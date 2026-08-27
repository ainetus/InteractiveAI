"""
ScenarioPlayer.py — Runs scripted Flatland scenarios.

A scenario defines:
- A Flatland map + timetable
- Events (things that happen at specific timesteps)
- Decision points (where simulation pauses for operator input)
- Pre-scripted action sequences for each decision option

The player steps through the simulation, triggers events and decision
points at the right timesteps, and applies pre-scripted actions after
a decision is made.
"""

import threading
from Corridor_environment import load_corridor_env
from FlatlandMapLoader import load_flatland_env_from_json
from TimetableDispatcher import TimetableDispatcher
from ScenarioManager import ScenarioManager


class ScenarioState:
    RUNNING   = "running"
    PAUSED    = "paused_for_decision"
    EVENT     = "event_triggered"
    COMPLETE  = "complete"


class ScenarioPlayer:
    """
    Plays back a scripted scenario step by step.

    Usage:
        player = ScenarioPlayer(scenario_dict)
        player.start()          # begin stepping in background thread
        player.apply_decision(option_index)  # at a decision point
        player.get_frame()      # current agent positions
    """

    def __init__(self, scenario: dict, on_event=None):
        import copy
        self.scenario   = copy.deepcopy(scenario)  # deep copy so _triggered flag resets each session
        self.on_event   = on_event  # callback(event_dict) when event triggers
        self.state      = ScenarioState.RUNNING
        self.step       = 0
        self.lock       = threading.Lock()
        self.running    = False
        self.speed      = 1.0

        # Active decision — set when simulation pauses
        self.active_decision = None  # the decision_point dict
        self.decision_index  = 0    # which decision_point we're at

        # Post-decision scripted actions
        # Format: {train_id: [action, action, ...]} for remaining steps
        self._scripted_actions = None
        self._scripted_step    = 0

        # Holds — {train_id: steps_remaining}
        self._holds = {}

        # Load environment
        map_path = scenario["map"]
        if map_path.endswith(".json"):
            env, stations, junctions = load_flatland_env_from_json(
                json_path=map_path,
                agent_defs=scenario.get("agent_defs", []),
            )
        else:
            env, stations, junctions = load_corridor_env(map_path)
        self.env      = env
        self.stations = stations

        # Set up timetable
        if map_path.endswith(".json"):
            # JSON scenario: build timetable directly from agent_defs
            from FlatlandMapLoader import build_timetable_from_env
            timetable, train_infos, _ = build_timetable_from_env(env, stations)
        else:
            # PKL scenario: use ScenarioManager with pre-built timetable
            manager = ScenarioManager(env, stations, junctions)
            timetable, train_infos, _ = manager.load_scenario_manual(
                scenario.get("scenario_index", 0)
            )
        self.dispatcher = TimetableDispatcher(
            env, timetable,
            train_infos=train_infos,
            enable_random_delays=False,
        )

        # Cached renderer — created once, reused per request
        from flatland.utils.rendertools import RenderTool
        self.renderer = RenderTool(env, gl="PILSVG", screen_width=600, screen_height=600)

        # History of agent states per step — for ZWL diagram
        self._history: list = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        """Start the simulation loop in a background thread."""
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def pause(self):
        with self.lock:
            self.running = False

    def resume(self):
        with self.lock:
            self.running = True

    def apply_decision(self, option_index: int):
        """
        Apply the operator's chosen option at the current decision point.
        Resumes the simulation with the pre-scripted outcome.
        """
        with self.lock:
            if self.active_decision is None:
                return False
            if option_index < 0 or option_index >= len(self.active_decision["options"]):
                return False

            option  = self.active_decision["options"][option_index]
            outcome = option.get("outcome", {})

            # Apply hold if defined
            hold_train = outcome.get("hold_train")
            hold_steps = outcome.get("hold_steps", 0)
            if hold_train and hold_steps > 0:
                self._holds[hold_train] = hold_steps
            # Support holding multiple trains with same duration
            for t in outcome.get("hold_trains", []):
                if hold_steps > 0:
                    self._holds[t] = hold_steps
            # Support per-train hold durations via holds dict
            for t, steps in outcome.get("holds", {}).items():
                if steps > 0:
                    self._holds[t] = steps

            # Apply pre-scripted actions if defined
            scripted = outcome.get("scripted_actions")
            if scripted:
                self._scripted_actions = scripted
                self._scripted_step    = 0

            self.active_decision = None
            self.state           = ScenarioState.RUNNING
            self.running         = True

        return True

    def get_history_steps(self) -> list:
        """Return full history of agent states — for ZWL Marey diagram."""
        with self.lock:
            return list(self._history)

    def get_frame(self) -> dict:
        """Current agent states — same format as _step_to_dict in flatland-hmi."""
        with self.lock:
            result = {}
            for agent in self.env.agents:
                result[str(agent.handle)] = {
                    "position":  (
                        [int(c) for c in agent.position]
                        if agent.position is not None else None
                    ),
                    "direction": int(agent.direction) if agent.direction is not None else 0,
                    "moving":    bool(agent.moving) if hasattr(agent, "moving") else False,
                    "target":    (
                        [int(c) for c in agent.target]
                        if agent.target is not None else None
                    ),
                    "malfunction": 0,
                }
            return result

    def get_affected_trains(self) -> set:
        """Return set of train IDs currently affected by an event (for red highlight)."""
        with self.lock:
            return set(self._holds.keys())

    def get_status(self) -> dict:
        with self.lock:
            result = {
                "state":            self.state,
                "step":             self.step,
                "active_decision":  None,
                "scenario_name":    self.scenario.get("name", ""),
                "affected_trains":  list(self._holds.keys()),
            }
            if self.active_decision is not None:
                result["active_decision"] = {
                    "description": self.active_decision.get("description", ""),
                    "options": [
                        {
                            "index":  i,
                            "label":  opt["label"],
                            "kpis":   opt["kpis"],
                        }
                        for i, opt in enumerate(self.active_decision["options"])
                    ],
                }
            return result

    def get_transitions(self) -> list:
        """Rail grid for ZWL diagram."""
        return self.env.rail.grid.tolist()

    # ── Internal loop ──────────────────────────────────────────────────────────

    def _loop(self):
        import time
        while True:
            try:
                with self.lock:
                    running   = self.running
                    speed     = self.speed
                    cur_state = self.state

                if cur_state == ScenarioState.COMPLETE:
                    print("[ScenarioPlayer] Scenario complete, loop exiting")
                    break

                if not running or cur_state == ScenarioState.PAUSED:
                    time.sleep(0.1)
                    continue

                self._advance()
                time.sleep(1.0 / max(speed, 0.1))

            except Exception as e:
                import traceback
                print("[ScenarioPlayer] Loop error:", e)
                traceback.print_exc()
                time.sleep(0.5)  # Brief pause before retrying

    def _advance(self):
        """Advance one simulation step."""
        with self.lock:
            step = self.step

        # Check for events at this timestep
        for event in self.scenario.get("events", []):
            if event["timestep"] == step and not event.get("_triggered", False):
                event["_triggered"] = True
                self._on_event(event)

        # Check for decision points at this timestep
        decision_points = self.scenario.get("decision_points", [])
        if self.decision_index < len(decision_points):
            dp = decision_points[self.decision_index]
            if dp["timestep"] == step:
                with self.lock:
                    self.active_decision  = dp
                    self.decision_index  += 1
                    self.state           = ScenarioState.PAUSED
                    self.running         = False
                return

        # Build actions for this step
        actions = self._build_actions(step)

        # Step the environment
        try:
            self.env.step(actions)
        except Exception as e:
            print("[ScenarioPlayer] step error:", e)
            return

        with self.lock:
            self.step = step + 1

        # Record step for ZWL history
        frame = {}
        for agent in self.env.agents:
            frame[str(agent.handle)] = {
                "position":  (
                    [int(c) for c in agent.position]
                    if agent.position is not None else None
                ),
                "direction": int(agent.direction) if agent.direction is not None else 0,
                "moving":    bool(agent.moving) if hasattr(agent, "moving") else False,
                "target":    (
                    [int(c) for c in agent.target]
                    if agent.target is not None else None
                ),
                "malfunction": 0,
            }
        with self.lock:
            self._history.append(frame)

        # Check if simulation is complete (all agents done)
        if self.env.dones.get("__all__", False):
            with self.lock:
                self.state   = ScenarioState.COMPLETE
                self.running = False

    def _build_actions(self, step: int) -> dict:
        """Build action dict — scripted actions override dispatcher."""
        # Start with dispatcher actions
        try:
            actions = self.dispatcher.get_actions(step)
        except Exception:
            actions = {}

        # Apply holds — held trains get DO_NOTHING action
        DO_NOTHING = 4  # RailEnvActions.DO_NOTHING
        with self.lock:
            holds = dict(self._holds)

        for agent in self.env.agents:
            handle = agent.handle
            train_id = "Train_" + str(handle)
            if train_id in holds and holds[train_id] > 0:
                actions[handle] = DO_NOTHING
                with self.lock:
                    self._holds[train_id] -= 1
                    if self._holds[train_id] <= 0:
                        del self._holds[train_id]

        # Apply scripted actions if active
        if self._scripted_actions is not None:
            scripted_step = self._scripted_step
            for train_id, action_seq in self._scripted_actions.items():
                handle = int(train_id.replace("Train_", ""))
                if scripted_step < len(action_seq):
                    actions[handle] = action_seq[scripted_step]

            self._scripted_step += 1
            # Clear scripted actions when exhausted
            max_len = max(
                (len(seq) for seq in self._scripted_actions.values()),
                default=0
            )
            if self._scripted_step >= max_len:
                self._scripted_actions = None
                self._scripted_step    = 0

        return actions

    def _on_event(self, event: dict):
        """Called when an event timestep is reached."""
        event_type = event.get("type")
        if event_type == "train_delay":
            train_id   = event.get("train")
            hold_steps = event.get("duration", 0)
            if train_id and hold_steps > 0:
                with self.lock:
                    self._holds[train_id] = hold_steps

        # Fire callback so app.py can push the notification card
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception as e:
                print("[ScenarioPlayer] on_event callback error:", e)
