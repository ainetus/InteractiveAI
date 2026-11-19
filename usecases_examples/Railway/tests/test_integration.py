"""
Tests for the platform integration: Publisher (token reuse, request paths), the run list, the
SessionRunner (contexts on change, pause at the decision, apply, next, stop) and the HTTP app.
No platform needed: requests_mock stands in for it, a recording publisher for the runner.
"""

import os
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import create_app                                          # noqa: E402
from experiment_scenarios import ALL_SCENARIOS                      # noqa: E402
from integration.loop import READY, Conflict, SessionRunner         # noqa: E402
from integration.publisher import Publisher                         # noqa: E402
from integration.session import MODES, experiment_runs, single_run  # noqa: E402
from sim.scenario_player import COMPLETE, PAUSED, RUNNING           # noqa: E402

BASE = "http://platform"


# ── Publisher ─────────────────────────────────────────────────────────────

class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def platform(requests_mock):
    requests_mock.post(BASE + "/auth/token", json={"access_token": "t1", "token_type": "Bearer",
                                                   "expires_in": 300})
    requests_mock.post(BASE + "/cab_event/api/v1/events", json={"id": "e"}, status_code=201)
    requests_mock.post(BASE + "/cabcontext/api/v1/contexts", json={"id_context": "c"}, status_code=201)
    return requests_mock


def paths(requests_mock):
    return [r.path for r in requests_mock.request_history]


def test_publisher_reuses_one_token(platform):
    publisher = Publisher(BASE, "publisher_test", "test", clock=Clock())
    for _ in range(5):
        publisher.send_context({"use_case": "Railway"})
    publisher.send_event({"use_case": "Railway"})
    assert paths(platform) == ["/auth/token"] + ["/cabcontext/api/v1/contexts"] * 5 + ["/cab_event/api/v1/events"]
    assert platform.request_history[1].headers["Authorization"] == "Bearer t1"
    login = platform.request_history[0]
    assert "username=publisher_test" in login.text and "clientId=opfab-client" in login.text


def test_publisher_renews_the_token_before_it_expires(platform):
    clock = Clock()
    publisher = Publisher(BASE, "publisher_test", "test", clock=clock)
    publisher.send_context({})
    clock.now = 269                      # 300 s token, renewed 30 s early
    publisher.send_context({})
    clock.now = 271
    publisher.send_context({})
    assert paths(platform).count("/auth/token") == 2


def test_publisher_logs_in_again_after_a_401(platform):
    platform.post(BASE + "/cabcontext/api/v1/contexts",
                  [{"status_code": 401}, {"json": {}, "status_code": 201}])
    Publisher(BASE, "publisher_test", "test", clock=Clock()).send_context({})
    assert paths(platform) == ["/auth/token", "/cabcontext/api/v1/contexts",
                               "/auth/token", "/cabcontext/api/v1/contexts"]


# ── run list ──────────────────────────────────────────────────────────────

def test_experiment_has_every_scenario_three_per_mode_and_is_seeded():
    ids = list(ALL_SCENARIOS)
    runs = experiment_runs("session-a", ids)
    assert sorted(r["scenario_id"] for r in runs) == sorted(ids)
    modes = [r["mode"] for r in runs]
    assert modes[:3] == [modes[0]] * 3 and modes[3:] == [modes[3]] * 3 and modes[0] != modes[3]
    assert experiment_runs("session-a", ids) == runs
    others = {tuple((r["scenario_id"], r["mode"]) for r in experiment_runs(f"s{i}", ids)) for i in range(20)}
    assert len(others) > 1
    assert {experiment_runs(f"s{i}", ids)[0]["mode"] for i in range(20)} == set(MODES)


def test_single_run_rejects_an_unknown_mode():
    with pytest.raises(ValueError):
        single_run("scenario3", "free")


# ── SessionRunner ─────────────────────────────────────────────────────────

class RecordingPublisher:
    def __init__(self):
        self.events, self.contexts = [], []

    def send_event(self, payload):
        self.events.append(payload)

    def send_context(self, payload):
        self.contexts.append(payload)


def make_runner(steps_per_second=1.0):
    publisher = RecordingPublisher()
    return SessionRunner(publisher, steps_per_second=steps_per_second, sleep=lambda s: None), publisher


def tick_until(runner, state, limit=500):
    for _ in range(limit):
        if runner.player.state == state:
            return
        runner.tick()
    raise AssertionError(f"never reached {state}, at {runner.describe()}")


def scenario(context):
    return context["data"]["scenario"]


def test_start_posts_run_one_as_ready_and_does_not_step():
    runner, pub = make_runner()
    session = runner.start_session("S1", single_run("scenario3", "colearning"))
    assert session["scenario_position"] == 0 and session["ended_at"] is None
    assert [scenario(c)["state"] for c in pub.contexts] == [READY]
    first = pub.contexts[0]["data"]
    assert first["session"]["session_id"] == "S1" and first["infra"]["rows"] == 15
    assert scenario(pub.contexts[0])["mode"] == "colearning"
    runner.tick()
    assert runner.player.step_index == 0 and len(pub.contexts) == 1


def test_a_run_pauses_at_its_decision_and_the_choice_resumes_it():
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario3", "recommendation"))
    runner.next_run()
    assert (scenario(pub.contexts[-1])["state"], scenario(pub.contexts[-1])["step"]) == (RUNNING, 0)

    tick_until(runner, PAUSED)
    paused = pub.contexts[-1]
    assert scenario(paused)["state"] == PAUSED and scenario(paused)["decision_open"] is True
    card = pub.events[-1]["data"]
    assert (card["scenario_id"], card["decision_index"], card["timestep"], card["session_id"], card["run_mode"]) == \
        ("scenario3", 0, 16, "S1", "recommendation")

    sent = len(pub.contexts)
    for _ in range(10):
        runner.tick()
    assert len(pub.contexts) == sent and runner.player.state == PAUSED     # nothing sent while paused

    with pytest.raises(Conflict):
        runner.apply({"scenario_id": "scenario1", "decision_index": 0, "option_index": 0})
    with pytest.raises(Conflict):
        runner.apply({"scenario_id": "scenario3", "decision_index": 0, "option_index": 9})
    record = runner.apply({"scenario_id": "scenario3", "decision_index": 0, "option_index": 2}, "ev-1")
    assert (record["option_index"], record["source"], record["event_id"]) == (2, "recommendation", "ev-1")
    resumed = pub.contexts[-1]["data"]
    assert scenario(pub.contexts[-1])["state"] == RUNNING and resumed["decisions"][0]["option_index"] == 2
    with pytest.raises(Conflict):           # a second click
        runner.apply({"scenario_id": "scenario3", "decision_index": 0, "option_index": 2})


def test_colearning_choice_is_recorded_with_train_and_action():
    runner, _ = make_runner()
    runner.start_session("S1", single_run("scenario3", "colearning"))
    runner.next_run()
    tick_until(runner, PAUSED)
    record = runner.apply({"scenario_id": "scenario3", "decision_index": 0, "option_index": 1,
                           "train": "Train_1", "action": "vorfahrt"})
    assert (record["source"], record["train"], record["action"]) == ("colearning", "Train_1", "vorfahrt")


@pytest.mark.parametrize("sid", sorted(ALL_SCENARIOS))
def test_request_budget_per_scenario(sid):
    runner, pub = make_runner(steps_per_second=1.0)
    runner.start_session("S1", single_run(sid, "recommendation"))
    runner.next_run()
    tick_until(runner, PAUSED)
    runner.apply({"scenario_id": sid, "decision_index": 0, "option_index": 0})
    tick_until(runner, COMPLETE)
    assert 1 <= len(pub.events) <= 5      # scenario 3: its conflict card only; scenario 1: 3 cards, 2 ends (F-36)
    assert len(pub.contexts) <= 25                              # ≈ 10–20 per scenario (D7)
    states = [scenario(c)["state"] for c in pub.contexts]
    assert states[0] == READY and states[-1] == COMPLETE and states.count(PAUSED) == 1
    # every N steps while moving, N steps ≈ one 5 s poll
    steps = [scenario(c)["step"] for c in pub.contexts if scenario(c)["state"] == RUNNING]
    assert all(b - a <= runner.context_every for a, b in zip(steps, steps[1:]))
    assert pub.contexts[-1]["data"]["session"]["ended_at"] is not None     # last run of the session


def test_next_moves_on_only_after_a_complete_run():
    runner, pub = make_runner(steps_per_second=4.0)
    runner.start_session("S1", experiment_runs("S1", ["scenario3", "scenario2"]))
    runner.next_run()
    with pytest.raises(Conflict):
        runner.next_run()
    first = runner.session["scenario_order"][0]
    tick_until(runner, PAUSED)
    runner.apply({"scenario_id": first["scenario_id"], "decision_index": 0, "option_index": 0})
    tick_until(runner, COMPLETE)
    assert pub.contexts[-1]["data"]["session"]["ended_at"] is None
    for _ in range(5):
        runner.tick()
    assert scenario(pub.contexts[-1])["state"] == COMPLETE      # waits for "next"
    session = runner.next_run()
    assert session["scenario_position"] == 1
    assert scenario(pub.contexts[-1])["id"] == session["scenario_order"][1]["scenario_id"]
    assert (scenario(pub.contexts[-1])["state"], scenario(pub.contexts[-1])["step"]) == (RUNNING, 0)


def test_end_run_completes_the_run_where_it_is_and_waits_for_next():
    runner, pub = make_runner(steps_per_second=4.0)
    runner.start_session("S1", experiment_runs("S1", ["scenario3", "scenario2"]))
    with pytest.raises(Conflict):           # run 1 not started yet
        runner.end_run()
    runner.next_run()
    first = runner.session["scenario_order"][0]
    tick_until(runner, PAUSED)
    session = runner.end_run()
    ended = pub.contexts[-1]["data"]
    assert scenario(pub.contexts[-1])["state"] == COMPLETE and not ended["scenario"]["decision_open"]
    assert session["ended_at"] is None and ended["decisions"] == []     # left unanswered
    with pytest.raises(Conflict):           # the open decision is gone
        runner.apply({"scenario_id": first["scenario_id"], "decision_index": 0, "option_index": 0})
    with pytest.raises(Conflict):           # already complete
        runner.end_run()
    sent = len(pub.contexts)
    runner.tick()
    assert len(pub.contexts) == sent        # waits for "next"
    assert runner.next_run()["scenario_position"] == 1


def test_end_run_of_the_last_run_ends_the_session():
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario3", "recommendation"))
    runner.next_run()
    runner.tick()
    assert runner.end_run()["ended_at"] is not None
    assert scenario(pub.contexts[-1])["state"] == COMPLETE and pub.contexts[-1]["data"]["session"]["ended_at"]
    with pytest.raises(Conflict):
        runner.end_run()


def test_stop_ends_the_session_without_completing_the_run():
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario3", "recommendation"))
    runner.next_run()
    runner.tick()
    session = runner.stop_session()
    assert session["ended_at"] is not None
    assert scenario(pub.contexts[-1])["state"] == RUNNING and pub.contexts[-1]["data"]["session"]["ended_at"]
    sent = len(pub.contexts)
    runner.tick()
    assert len(pub.contexts) == sent
    with pytest.raises(Conflict):
        runner.stop_session()


def test_a_new_login_ends_the_running_session_and_the_same_login_is_refused():
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario3", "recommendation"))
    with pytest.raises(Conflict):
        runner.start_session("S1", single_run("scenario3", "recommendation"))
    runner.start_session("S2", single_run("scenario2", "colearning"))
    ended, started = pub.contexts[-2]["data"]["session"], pub.contexts[-1]["data"]["session"]
    assert (ended["session_id"], started["session_id"]) == ("S1", "S2")
    assert ended["ended_at"] is not None and started["ended_at"] is None


def test_the_same_login_playing_a_scenario_again_gets_new_event_ids(monkeypatch):
    """F-9: the Event Service merges events with the same id_event, id_train and event_type."""
    import integration.session
    starts = iter(["2026-11-17T10:00:00.000001+00:00", "2026-11-17T10:30:00.000002+00:00"])
    monkeypatch.setattr(integration.session, "now_iso", lambda: next(starts))
    runner, pub = make_runner()
    ids = []
    for _ in range(2):
        runner.start_session("S1", single_run("scenario3", "recommendation"))
        runner.next_run()
        tick_until(runner, PAUSED)
        ids.append([e["data"]["id_event"] for e in pub.events])
        pub.events.clear()
        runner.stop_session()
    assert ids[0] and len(ids[0]) == len(ids[1])
    assert not set(ids[0]) & set(ids[1])
    assert all(i.startswith("S1_20261117100000000001") for i in ids[0])


def test_a_slow_publisher_does_not_hold_up_the_session_controls():
    """F-12: a send that hangs blocks only its own call; the others queue behind it, in order."""
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario3", "recommendation"))
    gate, sending = threading.Event(), threading.Event()
    fast = pub.send_context

    def slow(payload):
        sending.set()
        assert gate.wait(10)
        fast(payload)
    pub.send_context = slow
    nxt = threading.Thread(target=runner.next_run)
    nxt.start()
    assert sending.wait(5)                          # next_run's context hangs in the publisher

    def controls():                                 # the steps and the choice go on meanwhile
        tick_until(runner, PAUSED)
        runner.apply({"scenario_id": "scenario3", "decision_index": 0, "option_index": 2})
    others = threading.Thread(target=controls)
    others.start()
    others.join(5)
    held_up = others.is_alive()
    gate.set()
    others.join(5)
    nxt.join(5)
    assert not held_up
    states = [scenario(c)["state"] for c in pub.contexts]
    assert states[:2] == [READY, RUNNING] and PAUSED in states and states[-1] == RUNNING
    steps = [scenario(c)["step"] for c in pub.contexts]
    assert steps == sorted(steps)


def test_an_event_ends_when_its_hold_runs_out():
    """F-36: the door fault of scenario 2 (step 3, 6 steps) is sent again at step 9, ended."""
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario2", "recommendation"))
    runner.next_run()
    sent_at, send = [], pub.send_event
    pub.send_event = lambda payload: (sent_at.append(runner.player.step_index), send(payload))
    tick_until(runner, PAUSED)                      # the decision at step 15
    assert sent_at == [4, 10, 15]                   # after the steps 3 and 9, at the pause at 15
    first, ended, conflict = pub.events
    assert "end_date" not in first and first["criticality"] == "HIGH"
    assert (ended["criticality"], ended["start_date"]) == ("ND", first["start_date"])
    assert ended["end_date"] >= first["start_date"]
    assert ended["data"] == first["data"]           # same id_event, id_train, event_type: one card
    assert ended["title"] == first["title"] and "end_date" not in conflict


def test_an_event_whose_end_the_run_does_not_reach_stays_unended():
    runner, pub = make_runner()
    runner.start_session("S1", single_run("scenario2", "recommendation"))
    runner.next_run()
    for _ in range(5):                              # the door fault at step 3, its end at 9
        runner.tick()
    runner.end_run()
    assert [e["criticality"] for e in pub.events] == ["HIGH"]


# ── HTTP app ──────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    runner, publisher = make_runner()
    app = create_app(runner)
    app.testing = True
    with app.test_client() as c:
        c.runner, c.publisher = runner, publisher
        yield c


def test_scenarios_route_lists_names_and_introductions(client):
    scenarios = client.get("/api/v1/scenarios").json
    assert [s["id"] for s in scenarios] == list(ALL_SCENARIOS)
    assert all(s["name"].startswith("Szenario") and s["introduction"] for s in scenarios)


def test_session_routes(client):
    assert client.get("/health").json == {"status": "ok"}
    response = client.post("/api/v1/session", json={"session_id": "S1", "kind": "experiment"})
    assert response.status_code == 201 and len(response.json["scenario_order"]) == 6
    assert client.post("/api/v1/session", json={"session_id": "S1"}).status_code == 409
    assert client.post("/api/v1/session/next").status_code == 200
    assert client.post("/api/v1/session/next").status_code == 409
    assert client.post("/api/v1/session/end-run").status_code == 200
    assert client.post("/api/v1/session/end-run").status_code == 409
    assert client.post("/api/v1/session/stop").status_code == 200
    assert client.post("/api/v1/session/stop").status_code == 409


def test_session_route_rejects_bad_input(client):
    assert client.post("/api/v1/session", json={}).status_code == 400
    assert client.post("/api/v1/session", json={"session_id": "S1", "kind": "x"}).status_code == 400
    assert client.post("/api/v1/session", json={"session_id": "S1", "kind": "single",
                                                "scenario_id": "nope", "mode": "colearning"}).status_code == 400
    assert client.post("/api/v1/session", data="text").status_code == 400


def test_recommendations_route_applies_the_open_decision_only(client):
    action = {"scenario_id": "scenario3", "decision_index": 0, "option_index": 1, "event_id": "ev"}
    assert client.post("/api/v1/recommendations", json=action).status_code == 409
    client.post("/api/v1/session", json={"session_id": "S1", "kind": "single",
                                         "scenario_id": "scenario3", "mode": "recommendation"})
    client.post("/api/v1/session/next")
    tick_until(client.runner, PAUSED)
    response = client.post("/api/v1/recommendations", json=action)
    assert response.status_code == 200 and response.json["applied"]["event_id"] == "ev"
    assert client.post("/api/v1/recommendations", json=action).status_code == 409
