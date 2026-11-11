"""
DRAFT payload builders for InteractiveAI (Railway use case).

Pure functions: player / scenario state in, JSON-ready dicts out. No HTTP.
The field names below are the proposed Railway contract (see
docs/plans/railway-use-case.md, section 4.1.2).

- context_payload()      -> POST /cabcontext/api/v1/contexts
- event_payload()        -> POST /cab_event/api/v1/events
- decision_event()       -> event for a decision point (the card the operator
                            clicks to get recommendations)
- recommendations()      -> agent response for POST /api/v1/recommendation

Session info passed in by the caller (integration/session.py):
    session = {"session_id": "...", "scenario_order": [{"scenario_id": "scenario3", "mode": "colearning"}, ...],
               "scenario_position": 0, "started_at": "...", "ended_at": None}
The running scenario's mode is the mode of scenario_order[scenario_position].
"""

from datetime import datetime, timezone
from typing import List, Optional

from integration.session import current_run
from sim.decisions import colearning_view, match_colearning
from sim.map_loader import load_map_json, station_markers
from sim.marey import link_map, marey_mapping, planned_paths

USE_CASE = "Railway"
EVENT_TYPE = "INFRASTRUCTURE"     # enum: PASSENGER, INFRASTRUCTURE, IMPACT, HARDWARE
CRITICALITY = "HIGH"
DECISION_EVENT_TITLE = "Entscheidung erforderlich"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def infra_payload(scenario: dict, timetable=None) -> dict:
    """
    Static part of the context (same for the whole scenario). Compute once, reuse.

    planned_paths needs the player's timetable (routes, planned departures); without it the
    field is empty.
    """
    raw = load_map_json(scenario["map"])
    link = scenario.get("marey_link")             # start / end cell of the line shown in the ZWL
    mapping = marey_mapping(raw["grid"], link["start"], link["end"]) if link else {}
    return {
        "map": scenario["map"],
        "rows": raw["gridDimensions"]["rows"],
        "cols": raw["gridDimensions"]["cols"],
        "grid": raw["grid"],                    # Flatland transition ints, row-major
        "stations": station_markers(scenario),
        "marey_link": link,
        "marey_mapping": mapping,               # "r,c" -> distance along the line
        "planned_paths": planned_paths(timetable, mapping) if timetable is not None else {},
        "link_map": link_map(raw["grid"], link["start"], link["end"], mapping) if link else None,
    }


def _decision_point_at(scenario: dict, timestep: int) -> Optional[int]:
    for i, dp in enumerate(scenario.get("decision_points", [])):
        if dp["timestep"] == timestep:
            return i
    return None


def context_payload(player, session: dict, infra: dict, state: Optional[str] = None) -> dict:
    """
    Full, self-contained snapshot (the frontend only ever sees the latest one).

    state overrides the player's state: "ready" before a run is started (Q29 a).
    """
    trains = []
    frame = player.frame()
    for tid, s in sorted(player.timetable.schedules.items()):
        key = f"Train_{tid}"
        f = frame[str(tid)]
        trains.append({
            "id_train": key,
            "name": s.name,
            "position": f["position"],
            "direction": f["direction"],
            "done": f["done"],
            "failure": key in player.affected_trains,   # held by an event/decision right now
            "planned_departure": s.planned_departure,
            "planned_arrival": s.planned_arrival,
            "actual_departure": s.actual_departure,
            "actual_arrival": s.actual_arrival,
            "delay": s.arrival_delay,
            "route": [list(c) for c in s.route],
        })
    return {
        "use_case": USE_CASE,
        "date": now_iso(),
        "data": {
            "session": session,
            "scenario": {
                "id": player.scenario.get("id"),
                "name": player.scenario.get("name"),
                "mode": current_run(session)["mode"],
                "step": player.step_index,
                "state": state or player.state,
                "decision_open": player.active_decision is not None,
            },
            "infra": infra,
            "trains": trains,
            "history": player.history,          # one frame per step, for the time-distance diagram
            "decisions": player.decisions,
        },
    }


def event_payload(player, event: dict, session: dict) -> Optional[dict]:
    """Scenario event -> InteractiveAI event. None if the scenario says push_card=False."""
    if not event.get("push_card", True):
        return None
    sc = player.scenario
    train = event.get("train", "")
    dp_index = _decision_point_at(sc, event["timestep"])
    return {
        "use_case": USE_CASE,
        "title": event.get("card_title", "Ereignis"),
        "description": event.get("card_description", ""),
        "criticality": CRITICALITY,
        "start_date": now_iso(),
        "data": {
            "id_event": f"{session.get('session_id', '')}_{sc.get('id')}_{event['timestep']}",
            "event_type": EVENT_TYPE,
            "id_train": train,
            "agent_id": train.replace("Train_", ""),
            "delay": int(event.get("duration", 0)),
            "scenario_id": sc.get("id"),
            "timestep": event["timestep"],
            "decision_index": dp_index,          # not None -> recommendations available on this card
            "session_id": session.get("session_id"),
        },
    }


def decision_event(player, dp_index: int, session: dict) -> Optional[dict]:
    """
    Event for a decision point that has no event at the same timestep
    (scenario 4: decision at 22, last event at 5). Returns None when a scenario
    event at that timestep already carries the decision (event_payload sets
    decision_index), so the operator gets one card, not two.
    """
    sc = player.scenario
    dp = sc["decision_points"][dp_index]
    if any(e["timestep"] == dp["timestep"] and e.get("push_card", True) for e in sc.get("events", [])):
        return None
    return {
        "use_case": USE_CASE,
        "title": DECISION_EVENT_TITLE,
        "description": dp.get("description", ""),
        "criticality": CRITICALITY,
        "start_date": now_iso(),
        "data": {
            "id_event": f"{session.get('session_id', '')}_{sc.get('id')}_{dp['timestep']}_decision",
            "event_type": EVENT_TYPE,
            "id_train": "",
            "agent_id": "",
            "delay": 0,
            "scenario_id": sc.get("id"),
            "timestep": dp["timestep"],
            "decision_index": dp_index,
            "session_id": session.get("session_id"),
        },
    }


def _kpis_as_strings(kpis: dict) -> dict:
    return {k: str(v) for k, v in kpis.items()}


def recommendations(scenario: dict, dp_index: int, mode: str, train_names: dict) -> List[dict]:
    """
    Agent response for one decision point. Needs no Flatland: the agent only
    reads the scenario definition (scenario_id + decision_index come from the event data).

    recommendation mode: one recommendation per scenario option.
    colearning mode:     one per train + action; infeasible ones are listed with
                         feasible="False", empty KPIs and the reason (old UI showed them as blocked).
    actions[0] tells the simulator what to apply: {"scenario_id", "decision_index", "option_index"}.
    """
    dp = scenario["decision_points"][dp_index]
    out = []
    if mode == "recommendation":
        for i, opt in enumerate(dp["options"]):
            out.append({
                "title": opt["label"],
                "description": dp.get("description", ""),
                "use_case": USE_CASE,
                "agent_type": "AI",
                "kpis": _kpis_as_strings(opt.get("kpis", {})),
                "actions": [{"scenario_id": scenario["id"], "decision_index": dp_index, "option_index": i}],
            })
        return out

    view = colearning_view(scenario, dp)
    for train in view["trains"]:
        for action in view["train_actions"].get(train, []):
            idx, reason = match_colearning(scenario, dp, train, action)
            label = view["train_labels"].get(train, train_names.get(train, train))
            title = f"{label}: {action}"
            if idx is None:
                out.append({"title": title, "description": reason, "use_case": USE_CASE,
                            "agent_type": "AI", "kpis": {"feasible": "False"}, "actions": []})
                continue
            out.append({
                "title": title,
                "description": dp["options"][idx]["label"],
                "use_case": USE_CASE,
                "agent_type": "AI",
                "kpis": {**_kpis_as_strings(dp["options"][idx].get("kpis", {})), "feasible": "True"},
                "actions": [{"scenario_id": scenario["id"], "decision_index": dp_index,
                             "option_index": idx, "train": train, "action": action}],
            })
    return out
