import copy
import json
import os

from experiment_scenarios.scenario1 import SCENARIO_1
from experiment_scenarios.scenario2 import SCENARIO_2
from experiment_scenarios.scenario3 import SCENARIO_3
from experiment_scenarios.scenario4 import SCENARIO_4
from experiment_scenarios.scenario5 import SCENARIO_5
from experiment_scenarios.scenario6 import SCENARIO_6

# the scenarios as written, with their hand-written KPIs (compute_kpis.py plays these)
RAW_SCENARIOS = {
    "scenario1": SCENARIO_1,
    "scenario2": SCENARIO_2,
    "scenario3": SCENARIO_3,
    "scenario4": SCENARIO_4,
    "scenario5": SCENARIO_5,
    "scenario6": SCENARIO_6,
}

KPIS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kpis.json")


def option_kpis(kpis: dict) -> dict:
    """An option's KPIs as the recommendations show them: the delay summed and per train
    ("delay:<train name>") and the energy (F-21)."""
    return {"delay": kpis["delay"],
            **{f"delay:{name}": delay for name, delay in kpis["delay_per_train"].items()},
            "energy": kpis["energy"]}


def _with_computed_kpis(scenarios: dict) -> dict:
    """
    The scenarios with each option's KPIs from kpis.json (compute_kpis.py), which replace the
    hand-written ones (F-21: they contradict the simulation); those stay as kpis_hand_written. An
    option missing in kpis.json keeps its hand-written KPIs.
    """
    if not os.path.exists(KPIS_FILE):
        return scenarios
    with open(KPIS_FILE, encoding="utf-8") as f:
        computed = json.load(f)
    out = copy.deepcopy(scenarios)
    for sid, scenario in out.items():
        for dp_index, dp in enumerate(scenario.get("decision_points", [])):
            for option_index, option in enumerate(dp["options"]):
                kpis = computed.get(f"{sid}/{dp_index}/{option_index}")
                if kpis is not None:
                    option["kpis_hand_written"] = option.get("kpis", {})
                    option["kpis"] = option_kpis(kpis)
    return out


ALL_SCENARIOS = _with_computed_kpis(RAW_SCENARIOS)
