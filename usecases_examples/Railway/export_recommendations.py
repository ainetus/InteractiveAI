"""
Write recommendations.json: every decision's recommendations, as RailwayManager returns them.

The Recommendation Service answers Railway's recommendation requests from its copy of this file
(backend/recommendation-service/resources/Railway/recommendations.json), looked up by the event's
scenario_id, decision_index and run_mode (Q2 a). Nothing is computed live: the options, their KPIs
and the Ko-Lernen choices are written into the scenario files, and payloads.recommendations()
reshapes them into the platform's response format.

    {"<scenario_id>/<decision_index>/<mode>": [recommendation, ...], ...}

Run after changing a scenario, from this folder; it writes both files:

    python export_recommendations.py

tests/test_recommendations.py checks that both files equal this script's output.
"""

import json
import os

from experiment_scenarios import ALL_SCENARIOS
from integration import payloads
from integration.session import MODES

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "recommendations.json")
SERVICE_COPY = os.path.join(HERE, "..", "..", "backend", "recommendation-service", "resources",
                            "Railway", "recommendations.json")


def build() -> dict:
    out = {}
    for sid, scenario in ALL_SCENARIOS.items():
        # train names as ScenarioPlayer gives them
        names = {f"Train_{i}": d.get("name", f"Train_{i}") for i, d in enumerate(scenario["agent_defs"])}
        for index in range(len(scenario.get("decision_points", []))):
            for mode in MODES:
                out[f"{sid}/{index}/{mode}"] = payloads.recommendations(scenario, index, mode, names)
    return out


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    text = render(build())
    for path in (OUTPUT, SERVICE_COPY):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {os.path.normpath(path)}")
