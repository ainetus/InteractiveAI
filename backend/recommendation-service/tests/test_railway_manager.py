"""RailwayManager: the scripted simulator's decisions from recommendations.json, the catalog for
every other event (unchanged)."""

import json

from resources.Railway.manager import SCENARIO_RECOMMENDATIONS_FILE, RailwayManager


def ask(**event):
    return RailwayManager().get_recommendation({"event": event, "context": {}})


def entry(key):
    with open(SCENARIO_RECOMMENDATIONS_FILE, encoding="utf-8") as f:
        return json.load(f)[key]


def test_decision_of_the_simulator_gets_its_entry():
    recos = ask(scenario_id="scenario3", decision_index=0, run_mode="colearning", mode=None)
    assert recos == entry("scenario3/0/colearning")
    assert recos[0]["actions"][0]["scenario_id"] == "scenario3"


def test_both_modes_have_their_own_entry():
    recommendation = ask(scenario_id="scenario1", decision_index=0, run_mode="recommendation")
    colearning = ask(scenario_id="scenario1", decision_index=0, run_mode="colearning")
    assert [r["title"] for r in recommendation] == [
        "S 18 Vorfahrt — S 17 und IC 3 warten",
        "IC 3 Vorfahrt — S 17 folgt nach 5, S 18 wartet",
        "S 17 Vorfahrt — S 18 wartet, IC 3 wartet",
    ]
    assert recommendation[1]["kpis"] == {"local_delay": "28", "global_delay": "20", "energy": "80",
                                         "anschluss": "2"}
    assert colearning != recommendation and any("train" in r["actions"][0] for r in colearning if r["actions"])


def test_card_without_decision_or_unknown_key_gets_nothing():
    assert ask(scenario_id="scenario1", decision_index=None, run_mode="recommendation") == []
    assert ask(scenario_id="scenario9", decision_index=0, run_mode="recommendation") == []
    assert ask(scenario_id="scenario1", decision_index=0) == []


def test_events_without_scenario_id_still_get_the_catalog():
    recos = ask(id_event="1", event_type="INFRASTRUCTURE", mode="basic")
    assert recos and all(r["use_case"] == "Railway" for r in recos)
