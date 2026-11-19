"""
ScenarioPlayer - plays one scripted experiment scenario, step by step, headless.

A scenario (experiment_scenarios/scenarioN.py) defines:
- map + agent_defs (start, target, dir, dep, arr, name, speed)
- events: things that happen at a timestep (delay holds, info cards)
- decision_points: the simulation pauses; each option has fixed KPIs and a
  scripted outcome (holds per train and/or scripted Flatland actions)

The player has no thread, no timer and no network. The caller drives it:

    player = ScenarioPlayer(scenario, hooks=Hooks(on_event=..., on_decision=...))
    while player.state != COMPLETE:
        if player.state == PAUSED:
            ...wait for the operator's choice...
            player.apply_decision(i)
        player.step()

Hooks are where the InteractiveAI integration plugs in (send an event,
send a context, ...). They are called synchronously.

Behaviour per step is unchanged against the old threaded player (positions
identical in every scenario/option except scenario 5 option 0, see
decisions.normalize_holds).

Change against the handover's player: the holds of slow trains (speed < 1) are kept apart from
the holds of events and decisions (_speed_holds), so affected_trains names only trains that an
event or decision holds; a slow train was named there every other step (F-10). The steps are
unchanged: an event or decision hold still replaces a running speed hold, and no speed hold
starts while one of them runs.

Added: stopped_steps counts, per train, the steps it has stood still on the grid so far (its cell
the same as one step before, for whatever reason: an event, a decision, its slow speed, a train
ahead), shown as "Breakdown delay" in the train table (F-34).
"""

import copy
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .decisions import normalize_holds
from .dispatcher import STOP_MOVING, TimetableDispatcher
from .map_loader import build_routes, load_env
from .timetable import build_timetable

RUNNING = "running"
PAUSED = "paused_for_decision"
COMPLETE = "complete"

EPISODE_MARGIN = 50   # extra steps on top of the scenario's own time budget (K33)


@dataclass
class Hooks:
    on_event: Optional[Callable[["ScenarioPlayer", dict], None]] = None      # scenario event fired
    on_decision: Optional[Callable[["ScenarioPlayer", dict], None]] = None   # paused at a decision point
    on_resume: Optional[Callable[["ScenarioPlayer", dict], None]] = None     # decision applied (record)
    on_step: Optional[Callable[["ScenarioPlayer"], None]] = None             # after every env.step
    on_complete: Optional[Callable[["ScenarioPlayer"], None]] = None         # all trains done / episode end


def episode_limit(scenario: dict) -> int:
    """
    Flatland episode limit from the scenario itself (bugfix K33: was 200 for every map).
    Latest planned arrival + all event holds + the longest option outcome + margin.
    """
    defs = scenario["agent_defs"]
    budget = max(d["arr"] for d in defs)
    budget += sum(e.get("duration", 0) for e in scenario.get("events", []))
    for dp in scenario.get("decision_points", []):
        extra = 0
        for opt in dp.get("options", []):
            o = opt.get("outcome", {})
            scripted = max((len(s) for s in o.get("scripted_actions", {}).values()), default=0)
            extra = max(extra, sum(normalize_holds(o).values()) + scripted)
        budget += extra
    slow = sum(int(round(1 / d["speed"])) - 1 for d in defs if d.get("speed", 1.0) < 1.0)
    return budget * (1 + slow) + EPISODE_MARGIN


class ScenarioPlayer:

    def __init__(self, scenario: dict, hooks: Optional[Hooks] = None):
        self.scenario = copy.deepcopy(scenario)   # events get a _triggered flag
        self.hooks = hooks or Hooks()
        self.state = RUNNING
        self.step_index = 0

        self.active_decision: Optional[dict] = None
        self.decision_index = 0                   # next decision point to check
        self.decisions: List[dict] = []           # applied decisions (record)

        self._scripted_actions: Optional[Dict[str, List[int]]] = None
        self._scripted_step = 0
        self._holds: Dict[str, int] = {}          # {"Train_i": steps remaining}, events and decisions
        self._speed_holds: Dict[str, int] = {}    # the same for slow trains (speed < 1)
        self._speed_factors: Dict[str, float] = {}
        self._prev_positions: Dict[str, Optional[tuple]] = {}

        defs = self.scenario["agent_defs"]
        for i, d in enumerate(defs):
            if d.get("speed", 1.0) < 1.0:
                self._speed_factors[f"Train_{i}"] = d["speed"]

        self.env, self.stations = load_env(self.scenario["map"], defs, episode_limit(self.scenario))
        self.timetable = build_timetable(self.env, defs, build_routes(self.env, defs))
        self.dispatcher = TimetableDispatcher(self.env, self.timetable)
        self.train_names = {f"Train_{i}": d.get("name", f"Train_{i}") for i, d in enumerate(defs)}

        self.history: List[dict] = []             # one frame per step (time-distance diagram)
        self.stopped_steps: Dict[str, int] = {f"Train_{i}": 0 for i in range(len(defs))}

    # ── control ───────────────────────────────────────────────────────────

    def step(self):
        """Advance one simulation step (no-op while paused or complete)."""
        if self.state != RUNNING:
            return
        step = self.step_index

        for event in self.scenario.get("events", []):
            if event["timestep"] == step and not event.get("_triggered"):
                event["_triggered"] = True
                self._fire_event(event)

        dps = self.scenario.get("decision_points", [])
        if self.decision_index < len(dps) and dps[self.decision_index]["timestep"] == step:
            self.active_decision = dps[self.decision_index]
            self.decision_index += 1
            self.state = PAUSED
            if self.hooks.on_decision:
                self.hooks.on_decision(self, self.active_decision)
            return

        actions = self._build_actions(step)
        self.env.step(actions)
        self.dispatcher.record_arrivals(step)
        self._apply_speed_holds()
        self.step_index = step + 1
        self.history.append(self.frame())
        self._count_stopped()
        if self.hooks.on_step:
            self.hooks.on_step(self)

        if self.env.dones.get("__all__", False):
            self.state = COMPLETE
            if self.hooks.on_complete:
                self.hooks.on_complete(self)

    def apply_decision(self, option_index: int, source: str = "recommendation", meta: dict = None) -> bool:
        """Apply option `option_index` of the active decision point and resume."""
        if self.state != PAUSED or self.active_decision is None:
            return False
        options = self.active_decision["options"]
        if not 0 <= option_index < len(options):
            return False
        option = options[option_index]
        outcome = option.get("outcome", {})
        for train, steps in normalize_holds(outcome).items():
            self._hold(train, steps)
        if outcome.get("scripted_actions"):
            self._scripted_actions = outcome["scripted_actions"]
            self._scripted_step = 0

        record = {
            "scenario_id": self.scenario.get("id"),
            "decision_index": self.decision_index - 1,
            "timestep": self.active_decision.get("timestep"),
            "option_index": option_index,
            "option_label": option["label"],
            "kpis": option.get("kpis", {}),
            "source": source,                 # "recommendation" or "colearning"
            **(meta or {}),
        }
        self.decisions.append(record)
        self.active_decision = None
        self.state = RUNNING
        if self.hooks.on_resume:
            self.hooks.on_resume(self, record)
        return True

    # ── state for payloads ────────────────────────────────────────────────

    @property
    def affected_trains(self) -> List[str]:
        """Trains currently held by an event or decision (red highlight in the old UI)."""
        return sorted(self._holds)

    def frame(self) -> dict:
        """Current state of every train: {"0": {position, direction, moving, target, done}}."""
        out = {}
        for a in self.env.agents:
            out[str(a.handle)] = {
                "position": [int(c) for c in a.position] if a.position is not None else None,
                "direction": int(a.direction) if a.direction is not None else 0,
                "moving": bool(getattr(a, "moving", False)),
                "target": [int(c) for c in a.target] if a.target is not None else None,
                "done": "DONE" in a.state.name,
            }
        return out

    # ── internals ─────────────────────────────────────────────────────────

    def _fire_event(self, event: dict):
        if event.get("type") == "train_delay" and event.get("train") and event.get("duration", 0) > 0:
            self._hold(event["train"], event["duration"])
        if self.hooks.on_event:
            self.hooks.on_event(self, event)

    def _hold(self, train: str, steps: int):
        """An event's or decision's hold; it replaces the train's speed hold."""
        self._holds[train] = steps
        self._speed_holds.pop(train, None)

    def _build_actions(self, step: int) -> Dict[int, int]:
        """Dispatcher actions, then holds (STOP_MOVING), then scripted actions on top."""
        actions = self.dispatcher.get_actions(step)
        for agent in self.env.agents:
            train = f"Train_{agent.handle}"
            for holds in (self._holds, self._speed_holds):
                if holds.get(train, 0) > 0:
                    actions[agent.handle] = STOP_MOVING
                    holds[train] -= 1
                    if holds[train] <= 0:
                        del holds[train]
                    break
        if self._scripted_actions is not None:
            for train, seq in self._scripted_actions.items():
                if self._scripted_step < len(seq):
                    actions[int(train.replace("Train_", ""))] = seq[self._scripted_step]
            self._scripted_step += 1
            if all(self._scripted_step >= len(s) for s in self._scripted_actions.values()):
                self._scripted_actions = None
                self._scripted_step = 0
        return actions

    def _count_stopped(self):
        """A train on the grid in the same cell as after the step before has stood still."""
        if len(self.history) < 2:
            return
        before, now = self.history[-2], self.history[-1]
        for handle, state in now.items():
            position = state["position"]
            if position is not None and position == before[handle]["position"]:
                self.stopped_steps[f"Train_{handle}"] += 1

    def _apply_speed_holds(self):
        """speed < 1: after every move, hold the train round(1/speed) - 1 steps."""
        for i, agent in enumerate(self.env.agents):
            train = f"Train_{i}"
            if train not in self._speed_factors or agent.position is None:
                continue
            pos = tuple(agent.position)
            if pos != self._prev_positions.get(train) and train not in self._holds \
                    and train not in self._speed_holds:
                hold = round(1.0 / self._speed_factors[train]) - 1
                if hold > 0:
                    self._speed_holds[train] = hold
            self._prev_positions[train] = pos
