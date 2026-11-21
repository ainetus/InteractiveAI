"""recommendations.json and the Recommendation Service's copy equal export_recommendations.py's output."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import export_recommendations as export                              # noqa: E402
from experiment_scenarios import ALL_SCENARIOS                       # noqa: E402

FIX = "run `python export_recommendations.py` in usecases_examples/Railway"


def test_file_equals_the_script_output():
    with open(export.OUTPUT, encoding="utf-8") as f:
        assert f.read() == export.render(export.build()), FIX


def test_service_copy_equals_the_simulator_file():
    with open(export.OUTPUT, encoding="utf-8") as a, open(export.SERVICE_COPY, encoding="utf-8") as b:
        assert a.read() == b.read(), FIX


def test_every_decision_has_both_modes():
    data = json.loads(export.render(export.build()))
    keys = {f"{sid}/{i}/{mode}" for sid, sc in ALL_SCENARIOS.items()
            for i in range(len(sc["decision_points"])) for mode in ("recommendation", "colearning")}
    assert set(data) == keys
    for key, recos in data.items():
        sid, index, mode = key.split("/")
        options = ALL_SCENARIOS[sid]["decision_points"][int(index)]["options"]
        applicable = [r for r in recos if "option_index" in r["actions"][0]]
        assert all(r["kpis"]["feasible"] == "False" for r in recos if r not in applicable)
        assert applicable and all(r["actions"][0]["scenario_id"] == sid for r in applicable)
        assert all(0 <= r["actions"][0]["option_index"] < len(options) for r in applicable)
        if mode == "recommendation":
            assert len(recos) == len(options)
