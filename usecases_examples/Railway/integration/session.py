"""
Experiment session = one participant, one mode, all scenarios in a shuffled order.

Replaces SessionManager.py (SQLite). Nothing is stored here: the session dict
goes into every context and event (integration/payloads.py), so InteractiveAI
logs it together with the operator's actions.

Change against the old version: the order is shuffled with the participant
code as seed, so a session can be restarted with the same order
(old: random.shuffle, a new order on every start).
"""

import random
import uuid
from datetime import datetime, timezone
from typing import List


def make_session(participant: str, mode: str, scenario_ids: List[str]) -> dict:
    if mode not in ("recommendation", "colearning"):
        raise ValueError(f"unknown mode {mode!r}")
    order = list(scenario_ids)
    random.Random(participant).shuffle(order)
    return {
        "session_id": str(uuid.uuid4()),
        "participant": participant,
        "mode": mode,
        "scenario_order": order,
        "scenario_position": 0,          # index into scenario_order, set by the caller
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
