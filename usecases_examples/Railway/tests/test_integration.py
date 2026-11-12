"""
Tests for the platform integration: Publisher (token reuse, request paths), the run list, the
SessionRunner (contexts on change, pause at the decision, apply, next, stop) and the HTTP app.
No platform needed: requests_mock stands in for it, a recording publisher for the runner.
"""

import os
import sys

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
    assert 1 <= len(pub.events) <= 4                            # scenario 3 has only its conflict card
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
