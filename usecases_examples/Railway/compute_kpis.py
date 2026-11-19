"""
Compute the KPIs of every decision's options from the simulation (F-21) and write them to
experiment_scenarios/kpis.json, which replaces the scenario files' hand-written KPIs (F-21) in
the recommendations and the decision records (see experiment_scenarios/__init__.py).

Each option is played from the start of its scenario to the end (sim/kpis.py for the
definitions): delay in steps, summed and per train; energy as the steps all trains spend on the
grid.

Run after changing a scenario, from this folder, then export the recommendations:

    python compute_kpis.py            # writes kpis.json, prints computed vs hand-written
    python export_recommendations.py  # writes recommendations.json and the service's copy

tests/test_kpis.py checks that kpis.json equals this script's output.
"""

import json
import os

from experiment_scenarios import RAW_SCENARIOS
from sim.kpis import option_kpis

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "experiment_scenarios", "kpis.json")


def build() -> dict:
    """{"<scenario_id>/<decision_index>/<option_index>": kpis}"""
    out = {}
    for scenario in RAW_SCENARIOS.values():
        for row in option_kpis(scenario):
            out[f"{row['scenario_id']}/{row['decision_index']}/{row['option_index']}"] = row["kpis"]
    return out


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def table(data: dict) -> str:
    lines = [f"{'option':<14} {'delay':>5} {'energy':>6}   per train | hand-written"]
    for key, k in data.items():
        sid, dp, opt = key.split("/")
        hand = RAW_SCENARIOS[sid]["decision_points"][int(dp)]["options"][int(opt)].get("kpis", {})
        trains = ", ".join(f"{name} {delay}" for name, delay in k["delay_per_train"].items())
        late = f" (not arrived: {', '.join(k['not_arrived'])})" if k["not_arrived"] else ""
        lines.append(f"{key:<14} {k['delay']:>5} {k['energy']:>6}   {trains}{late} | {hand}")
    return "\n".join(lines)


if __name__ == "__main__":
    data = build()
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(render(data))
    print(table(data))
    print(f"wrote {os.path.normpath(OUTPUT)}")
