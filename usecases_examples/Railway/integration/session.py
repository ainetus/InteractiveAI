"""
Experiment session: one login, an ordered list of runs (scenario + mode).

Nothing is stored here: the session dict goes into every context (integration/payloads.py),
so InteractiveAI logs it together with the operator's actions.

The session id is the platform's trace session id (one login), sent by the start dialog; it
stands for the participant (no participant code, D10). It also seeds the run list, so the same
login gets the same order again (F29).
"""

import random
from datetime import datetime, timezone
from typing import List

MODES = ("recommendation", "colearning")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def experiment_runs(session_id: str, scenario_ids: List[str]) -> List[dict]:
    """
    As railway_sim's Experiment: the scenarios shuffled and split in two halves, the first half in
    a mode drawn at random, the second in the other (Q6, F39); seeded by the session id (F29).
    """
    rng = random.Random(session_id)
    order = list(scenario_ids)
    rng.shuffle(order)
    first = rng.choice(MODES)
    second = MODES[1 - MODES.index(first)]
    half = len(order) // 2
    return [{"scenario_id": sid, "mode": first if i < half else second} for i, sid in enumerate(order)]


def single_run(scenario_id: str, mode: str) -> List[dict]:
    """The single run of the start dialog: one scenario in one mode (Q13 d)."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    return [{"scenario_id": scenario_id, "mode": mode}]


def make_session(session_id: str, runs: List[dict]) -> dict:
    if not session_id:
        raise ValueError("session_id is required")
    if not runs:
        raise ValueError("a session needs at least one run")
    for run in runs:
        if run.get("mode") not in MODES:
            raise ValueError(f"unknown mode {run.get('mode')!r}")
    return {
        "session_id": session_id,
        "scenario_order": [dict(run) for run in runs],
        "scenario_position": 0,          # index into scenario_order
        "started_at": now_iso(),
        "ended_at": None,                # set after the last run or by "✕ Beenden"
    }


def current_run(session: dict) -> dict:
    return session["scenario_order"][session["scenario_position"]]
