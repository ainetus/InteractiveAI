"""The options' KPIs from the simulation (F-21): sim/kpis.py and compute_kpis.py's kpis.json."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import compute_kpis                                                  # noqa: E402
from experiment_scenarios import ALL_SCENARIOS, RAW_SCENARIOS        # noqa: E402
from sim.kpis import kpis, play                                      # noqa: E402

FIX = "run `python compute_kpis.py` and `python export_recommendations.py` in usecases_examples/Railway"


def test_kpis_file_equals_the_script_output():
    with open(compute_kpis.OUTPUT, encoding="utf-8") as f:
        assert f.read() == compute_kpis.render(compute_kpis.build()), FIX


def test_delay_is_the_train_tables_arrival_delay_summed():
    player = play(RAW_SCENARIOS["scenario4"], {0: 1})
    k = kpis(player)
    table = {s.name: s.arrival_delay for s in player.timetable.schedules.values()}
    assert k["delay_per_train"] == table and k["delay"] == sum(table.values())
    assert k["not_arrived"] == []


def test_energy_counts_each_trains_steps_on_the_grid():
    player = play(RAW_SCENARIOS["scenario3"], {0: 2})
    on_grid = sum(s.actual_arrival - s.actual_departure for s in player.timetable.schedules.values())
    # a train is on the grid from the step it appears on route[0] up to the one before it arrives
    assert kpis(player)["energy"] == on_grid


def test_the_scenarios_carry_the_computed_kpis():
    option = ALL_SCENARIOS["scenario6"]["decision_points"][0]["options"][0]
    assert option["kpis"] == {"delay": 5, "delay:IC 3": 5, "delay:S 12": 0, "delay:IR 35": 0,
                              "energy": 46}
    assert option["kpis_hand_written"]["anschluss"] == 0
    assert "kpis_hand_written" not in RAW_SCENARIOS["scenario6"]["decision_points"][0]["options"][0]
