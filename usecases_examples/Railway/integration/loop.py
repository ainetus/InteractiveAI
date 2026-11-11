"""
SessionRunner: plays a session's run list on the platform.

The ScenarioPlayer has no thread and no timer; this runner brings the loop back, without the
"Start", "Pause" and "Tempo" controls of railway_sim (Q4): it steps the running scenario at
RAILWAY_STEPS_PER_SECOND and sends what the hooks report through the Publisher.

- The participant does not control time (D8). A run pauses itself at its decision point and the
  applied choice resumes it (D19, Q25 b); there is no timeout and no default choice.
- Contexts are sent on change, not on a timer (D7): at the session start (run 1 "ready", Q29 a),
  when a run starts, at every event, at the decision, after the decision, at the end of a run,
  when the session ends, and every N steps while trains move (N steps ≈ one 5 s frontend poll).
  Nothing is sent while a run is paused or between runs.
- Between runs it waits for "next" (the start dialog's "Weiter", Q3 d). After the last run it sets
  session.ended_at; "✕ Beenden" sets it at any time, leaving the run's state as it is (Q26 a).
- One session at a time: a start with another session_id ends the running session first, a start
  with the same session_id is refused (Q29 a).

Limitations: one session per simulator process, so one participant at a time (Assumptions); a
context that fails to send is logged and not repeated, the next one replaces it.
"""

import copy
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from experiment_scenarios import ALL_SCENARIOS
from integration import payloads
from integration.session import current_run, make_session, now_iso
from sim.scenario_player import COMPLETE, PAUSED, RUNNING, Hooks, ScenarioPlayer

log = logging.getLogger(__name__)

READY = "ready"                 # scenario.state of a run that waits for "Weiter"
FRONTEND_POLL_S = 5.0           # the frontend reads the latest context every 5 s (stores/services.ts)


class Conflict(Exception):
    """A session control or choice that does not fit the current state (HTTP 409)."""


class SessionRunner:
    def __init__(self, publisher, scenarios: Optional[Dict[str, dict]] = None,
                 steps_per_second: float = 1.0, sleep: Callable[[float], None] = time.sleep):
        if steps_per_second <= 0:
            raise ValueError("steps_per_second must be positive")
        self.publisher = publisher
        self.scenarios = scenarios or ALL_SCENARIOS
        self.steps_per_second = steps_per_second
        self.context_every = max(1, round(FRONTEND_POLL_S * steps_per_second))
        self.sleep = sleep

        self.session: Optional[dict] = None
        self.player: Optional[ScenarioPlayer] = None
        self.infra: Optional[dict] = None
        self.ready = False              # the run waits for "next"

        self._lock = threading.RLock()
        self._dirty = False             # a hook asked for a context
        self._steps_since_context = 0
        self._stopped = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── session controls (HTTP app) ───────────────────────────────────────

    def start_session(self, session_id: str, runs: List[dict]) -> dict:
        for run in runs:
            if run.get("scenario_id") not in self.scenarios:
                raise ValueError(f"unknown scenario {run.get('scenario_id')!r}")
        with self._lock:
            if self._active():
                if self.session["session_id"] == session_id:
                    raise Conflict("this session is already running")
                self._end_session()                 # a session nobody ended (Q29 a)
            self.session = make_session(session_id, runs)
            self._load_run(0)
            self._send_context()
            return copy.deepcopy(self.session)

    def next_run(self) -> dict:
        with self._lock:
            if not self._active():
                raise Conflict("no running session")
            if not self.ready:
                if self.player.state != COMPLETE:
                    raise Conflict("the current run is not complete")
                position = self.session["scenario_position"] + 1
                if position >= len(self.session["scenario_order"]):
                    raise Conflict("no more runs")
                self.session["scenario_position"] = position
                self._load_run(position)
            self.ready = False
            self._send_context()
            return copy.deepcopy(self.session)

    def stop_session(self) -> dict:
        with self._lock:
            if not self._active():
                raise Conflict("no running session")
            self._end_session()
            return copy.deepcopy(self.session)

    def apply(self, action: dict, event_id: Optional[str] = None) -> dict:
        """Apply the operator's choice (actions[0] of a recommendation) to the open decision."""
        with self._lock:
            player = self.player
            if not self._active() or self.ready or player.state != PAUSED:
                raise Conflict("no open decision")
            open_index = player.decision_index - 1
            if action.get("scenario_id") != player.scenario.get("id") or \
                    action.get("decision_index") != open_index:
                raise Conflict(f"the open decision is {player.scenario.get('id')}/{open_index}")
            option_index = action.get("option_index")
            if not isinstance(option_index, int):
                raise ValueError("option_index must be an integer")
            colearning = action.get("train") is not None
            meta = {"train": action.get("train"), "action": action.get("action")} if colearning else {}
            if event_id:
                meta["event_id"] = event_id
            if not player.apply_decision(option_index, source="colearning" if colearning else "recommendation",
                                         meta=meta):
                raise Conflict(f"no option {option_index} at this decision")
            self._send_context()
            return copy.deepcopy(player.decisions[-1])

    # ── stepping ──────────────────────────────────────────────────────────

    def tick(self):
        """One step of the running scenario, and the contexts it calls for."""
        with self._lock:
            if not self._active() or self.ready or self.player.state != RUNNING:
                return
            self.player.step()
            if self.player.state == RUNNING:
                self._steps_since_context += 1
            if self._dirty or self._steps_since_context >= self.context_every:
                self._send_context()

    def run_forever(self):
        while not self._stopped.is_set():
            try:
                self.tick()
            except Exception:                       # keep the simulator up for the next session
                log.exception("step failed")
            self.sleep(1.0 / self.steps_per_second)

    def start(self):
        self._thread = threading.Thread(target=self.run_forever, name="railway-session", daemon=True)
        self._thread.start()

    def shutdown(self):
        self._stopped.set()

    # ── internals ─────────────────────────────────────────────────────────

    def _active(self) -> bool:
        return self.session is not None and self.session["ended_at"] is None

    def _load_run(self, position: int):
        scenario = self.scenarios[self.session["scenario_order"][position]["scenario_id"]]
        hooks = Hooks(on_event=self._on_event, on_decision=self._on_decision,
                      on_resume=self._on_resume, on_complete=self._on_complete)
        self.player = ScenarioPlayer(scenario, hooks)
        self.infra = payloads.infra_payload(scenario, self.player.timetable)
        self.ready = True

    def _end_session(self):
        self.session["ended_at"] = now_iso()
        self._send_context()

    def _on_event(self, player, event):
        self._send_event(payloads.event_payload(player, event, self.session))
        self._dirty = True

    def _on_decision(self, player, decision_point):
        self._send_event(payloads.decision_event(player, player.decision_index - 1, self.session))
        self._dirty = True

    def _on_resume(self, player, record):
        self._dirty = True

    def _on_complete(self, player):
        if self.session["scenario_position"] == len(self.session["scenario_order"]) - 1:
            self.session["ended_at"] = now_iso()
        self._dirty = True

    def _send_event(self, payload: Optional[dict]):
        if payload is None:
            return
        try:
            self.publisher.send_event(payload)
        except Exception:
            log.exception("event %s not sent", payload["data"].get("id_event"))

    def _send_context(self):
        self._dirty = False
        self._steps_since_context = 0
        payload = payloads.context_payload(self.player, self.session, self.infra,
                                           state=READY if self.ready else None)
        try:
            self.publisher.send_context(payload)
        except Exception:
            log.exception("context at step %s not sent", self.player.step_index)

    def describe(self) -> dict:
        """For logs and tests: where the session stands."""
        with self._lock:
            if self.session is None:
                return {"session": None}
            return {"session": copy.deepcopy(self.session), "run": current_run(self.session),
                    "state": READY if self.ready else self.player.state, "step": self.player.step_index}
