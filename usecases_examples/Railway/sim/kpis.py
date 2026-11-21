"""
KPIs of a decision's options, from the simulation itself (F-21): each option played from the start
of the scenario to its end, and measured.

- delay: each train's arrival delay as in the train table (actual - planned arrival, at least 0);
  a train that has not arrived at the episode end counts with its delay at that step. Per train
  and summed over all trains. In steps.
- energy: the steps all trains spend on the grid, from entering it (their departure) to reaching
  their target or the episode end, summed over all trains.

The scenario files' hand-written `kpis` (local_delay, global_delay, energy, anschluss, F-21) are
replaced by these (Q-33 a)); compute_kpis.py prints both side by side.
"""

from typing import Dict, List

from .scenario_player import COMPLETE, PAUSED, ScenarioPlayer


def play(scenario: dict, choices: Dict[int, int]) -> ScenarioPlayer:
    """Play the scenario to its end, applying option choices[i] at decision i (0 if not given)."""
    player = ScenarioPlayer(scenario)
    while player.state != COMPLETE:
        if player.state == PAUSED:
            player.apply_decision(choices.get(player.decision_index - 1, 0))
        player.step()
    return player


def kpis(player: ScenarioPlayer) -> dict:
    """The KPIs of a played-through scenario."""
    end = player.step_index
    per_train = {}
    not_arrived = []
    for schedule in player.timetable.schedules.values():
        if schedule.actual_arrival is not None:
            per_train[schedule.name] = schedule.arrival_delay
        else:
            per_train[schedule.name] = max(0, end - schedule.planned_arrival)
            not_arrived.append(schedule.name)
    energy = sum(1 for frame in player.history for state in frame.values() if state["position"] is not None)
    return {
        "delay": sum(per_train.values()),
        "delay_per_train": per_train,
        "not_arrived": not_arrived,
        "energy": energy,
        "steps": end,
    }


def option_kpis(scenario: dict) -> List[dict]:
    """The KPIs of every option of every decision, the other decisions at option 0."""
    rows = []
    for dp_index, dp in enumerate(scenario.get("decision_points", [])):
        for option_index, option in enumerate(dp["options"]):
            player = play(scenario, {dp_index: option_index})
            rows.append({"scenario_id": scenario["id"], "decision_index": dp_index,
                         "option_index": option_index, "label": option["label"],
                         "kpis": kpis(player), "hand_written": option.get("kpis", {})})
    return rows
