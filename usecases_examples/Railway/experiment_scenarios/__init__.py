"""
experiment_scenarios/__init__.py — All scripted scenarios.
"""

from experiment_scenarios.test_scenario import TEST_SCENARIO
from experiment_scenarios.scenario1 import SCENARIO_1
from experiment_scenarios.scenario2 import SCENARIO_2
from experiment_scenarios.scenario3 import SCENARIO_3

ALL_SCENARIOS = {
    "test":      TEST_SCENARIO,
    "scenario1": SCENARIO_1,
    "scenario2": SCENARIO_2,
    "scenario3": SCENARIO_3,
}
