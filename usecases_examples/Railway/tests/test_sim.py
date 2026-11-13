"""
Tests for the cleaned scripted simulator. Run from the package root: pytest -q

EXPECTED_ARRIVALS was recorded on 06.11.2026. Train positions at every step
were compared with the old threaded ScenarioPlayer (Flatland 4.2.6) and are
identical in every scenario/option except scenario5/0 (bugfix: hold_trains
was ignored -> deadlock). Arrival steps are one lower than the old code
would have recorded (bugfix K32).
"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from experiment_scenarios import ALL_SCENARIOS                      # noqa: E402
from integration import payloads                                    # noqa: E402
from integration.session import experiment_runs, make_session, single_run   # noqa: E402
from sim.decisions import colearning_view, match_colearning, normalize_holds   # noqa: E402
from sim.map_loader import load_map_json, station_markers          # noqa: E402
from sim.marey import link_map, marey_mapping                       # noqa: E402
from sim.scenario_player import COMPLETE, PAUSED, Hooks, ScenarioPlayer, episode_limit  # noqa: E402

EXPECTED_ARRIVALS = {
    "scenario1/0": {0: 74, 1: 72, 2: 76}, "scenario1/1": {0: 61, 1: 86, 2: 53}, "scenario1/2": {0: 60, 1: 83, 2: 82},
    "scenario2/0": {0: 24, 1: 35, 2: 28}, "scenario2/1": {0: 24, 1: 27, 2: 41},
    "scenario3/0": {0: 31, 1: 39, 2: 43}, "scenario3/1": {0: 32, 1: 27, 2: 35}, "scenario3/2": {0: 32, 1: 27, 2: 29},
    "scenario4/0": {0: 49, 1: 36, 2: 39}, "scenario4/1": {0: 34, 1: 48, 2: 51}, "scenario4/2": {0: 46, 1: 36, 2: 59},
    "scenario5/0": {0: 40, 1: 45, 2: 52}, "scenario5/1": {0: 50, 1: 35, 2: 61}, "scenario5/2": {0: 58, 1: 45, 2: 42},
    "scenario6/0": {0: 25, 1: 20, 2: 29}, "scenario6/1": {0: 25, 1: 27, 2: 29},
}


def play(sc, option_index, hooks=None):
    p = ScenarioPlayer(sc, hooks)
    for _ in range(2000):
        if p.state == COMPLETE:
            break
        if p.state == PAUSED:
            assert p.apply_decision(option_index)
            continue
        p.step()
    return p


@pytest.mark.parametrize("case", sorted(EXPECTED_ARRIVALS))
def test_arrivals_match_recorded_run(case):
    sid, opt = case.split("/")
    p = play(ALL_SCENARIOS[sid], int(opt))
    assert p.state == COMPLETE
    got = {tid: s.actual_arrival for tid, s in p.timetable.schedules.items()}
    assert got == EXPECTED_ARRIVALS[case]
    assert len(p.decisions) == 1 and p.decisions[0]["option_index"] == int(opt)


def test_every_option_of_every_scenario_is_covered():
    cases = {f"{sid}/{i}" for sid, sc in ALL_SCENARIOS.items()
             for i in range(len(sc["decision_points"][0]["options"]))}
    assert cases == set(EXPECTED_ARRIVALS)


def test_scenario5_option0_holds_both_trains():
    sc = ALL_SCENARIOS["scenario5"]
    p = ScenarioPlayer(sc)
    while p.state != PAUSED:
        p.step()
    p.apply_decision(0)
    assert p.affected_trains == ["Train_1", "Train_2"]


def test_normalize_holds_formats():
    assert normalize_holds({"holds": {"Train_0": 5}}) == {"Train_0": 5}
    assert normalize_holds({"hold_trains": ["Train_1", "Train_2"], "hold_steps": 10}) == {"Train_1": 10, "Train_2": 10}
    assert normalize_holds({"hold_train": "Train_3", "hold_steps": 4}) == {"Train_3": 4}
    assert normalize_holds({"scripted_actions": {"Train_0": [2]}}) == {}


def test_last_train_arrival_is_recorded():
    p = play(ALL_SCENARIOS["scenario6"], 0)
    assert all(s.actual_arrival is not None for s in p.timetable.schedules.values())


def test_names_and_planned_arrival_come_from_agent_defs():
    sc = ALL_SCENARIOS["scenario1"]
    p = ScenarioPlayer(sc)
    for i, d in enumerate(sc["agent_defs"]):
        assert p.timetable.schedules[i].name == d["name"]
        assert p.timetable.schedules[i].planned_arrival == d["arr"]


def test_episode_limit_covers_the_scenario():
    for sc in ALL_SCENARIOS.values():
        assert episode_limit(sc) > max(d["arr"] for d in sc["agent_defs"])


@pytest.mark.parametrize("sid", sorted(ALL_SCENARIOS))
def test_colearning_shows_the_kpis_it_applies(sid):
    sc = ALL_SCENARIOS[sid]
    dp = sc["decision_points"][0]
    view = colearning_view(sc, dp)
    for train, kpis in view["kpis_by_train"].items():
        idx, _ = match_colearning(sc, dp, train, "vorfahrt")
        assert dp["options"][idx]["kpis"] == kpis


def test_colearning_scenario3_trains_select_different_options():
    sc = ALL_SCENARIOS["scenario3"]
    dp = sc["decision_points"][0]
    assert [match_colearning(sc, dp, t, "vorfahrt")[0] for t in ("Train_0", "Train_1", "Train_2")] == [0, 1, 2]


def test_invalid_colearning_action_is_not_feasible():
    sc = ALL_SCENARIOS["scenario1"]
    idx, reason = match_colearning(sc, sc["decision_points"][0], "Train_0", "warten")
    assert idx is None and reason


@pytest.mark.parametrize("sid", sorted(ALL_SCENARIOS))
def test_payloads_are_json_and_one_card_per_decision(sid):
    sc = ALL_SCENARIOS[sid]
    session = make_session("S01", single_run(sid, "recommendation"))
    sent = []

    def on_event(p, e):
        sent.append(payloads.event_payload(p, e, session))

    def on_decision(p, dp):
        sent.append(payloads.decision_event(p, p.decision_index - 1, session))
        sent.append(payloads.context_payload(p, session, payloads.infra_payload(sc, p.timetable)))

    play(sc, 0, Hooks(on_event=on_event, on_decision=on_decision))
    sent = [s for s in sent if s is not None]
    json.dumps(sent)
    decision_cards = [s for s in sent if s.get("data", {}).get("decision_index") is not None]
    assert len(decision_cards) == 1
    for mode in ("recommendation", "colearning"):
        recos = payloads.recommendations(sc, 0, mode, {})
        json.dumps(recos)
        assert recos and all(r["use_case"] == "Railway" for r in recos)


def test_station_markers_include_every_train_start():
    for sc in ALL_SCENARIOS.values():
        starts = [m for m in station_markers(sc) if m.get("type") == "start"]
        assert [[m["r"], m["c"]] for m in starts] == [list(d["start"]) for d in sc["agent_defs"]]


def test_session_order_is_reproducible():
    ids = list(ALL_SCENARIOS)
    a = make_session("S07", experiment_runs("S07", ids))["scenario_order"]
    b = make_session("S07", experiment_runs("S07", ids))["scenario_order"]
    assert a == b and sorted(r["scenario_id"] for r in a) == sorted(ids)


@pytest.mark.parametrize("sid", sorted(ALL_SCENARIOS))
def test_marey_link_is_a_route_from_start_to_end(sid):
    sc = ALL_SCENARIOS[sid]
    link = sc["marey_link"]
    mapping = marey_mapping(load_map_json(sc["map"])["grid"], link["start"], link["end"])
    start, end = ",".join(map(str, link["start"])), ",".join(map(str, link["end"]))
    assert mapping[start] == 0
    # every distance from 0 to the end appears: a contiguous line
    assert sorted(set(mapping.values())) == list(range(mapping[end] + 1))


@pytest.mark.parametrize("sid", sorted(ALL_SCENARIOS))
def test_link_map_places_every_cell_in_three_rows(sid):
    sc = ALL_SCENARIOS[sid]
    link = sc["marey_link"]
    grid = load_map_json(sc["map"])["grid"]
    mapping = marey_mapping(grid, link["start"], link["end"])
    lm = link_map(grid, link["start"], link["end"], mapping)
    width = max(mapping.values()) + 1
    assert len(lm["grid"]) == 3 and all(len(row) == width for row in lm["grid"])
    on_line = [m for m in lm["mapping"] if m[1][0] == 1]
    assert len(on_line) == len(mapping)
    assert all(0 <= x < width and row in (0, 1, 2) for _, (row, x) in lm["mapping"])
    assert {tuple(cell) for cell, _ in lm["levels"]} == \
        {tuple(cell) for cell, (row, _) in lm["mapping"] if row != 1}


@pytest.mark.parametrize("sid", sorted(ALL_SCENARIOS))
def test_infra_has_planned_paths_on_the_line(sid):
    sc = ALL_SCENARIOS[sid]
    p = ScenarioPlayer(sc)
    infra = payloads.infra_payload(sc, p.timetable)
    json.dumps(infra)
    assert set(infra["planned_paths"]) == {f"Train_{t}" for t in p.timetable.schedules}
    distances = set(infra["marey_mapping"].values())
    for tid, points in infra["planned_paths"].items():
        steps = [step for step, _ in points]
        assert steps == sorted(steps)
        assert all(d in distances for _, d in points)
        dep = p.timetable.schedules[int(tid.split("_")[1])].planned_departure
        assert all(step >= dep for step in steps)

