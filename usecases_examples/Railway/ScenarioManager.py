"""
ScenarioManager.py — Single source of truth for scenario state.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from scenarios import make_scenarios
from safe_resolver import resolve_all_conflicts_safe, ResolutionResult
from Timetable import Timetable

# Path where learned resolutions are persisted between sessions
_LEARNED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "learned_resolutions.json")


@dataclass
class ScenarioInfo:
    index: int
    name: str
    description: str
    n_trains: int
    enable_random_delays: bool = False


class ScenarioManager:
    def __init__(self, env, stations: Dict, junctions: List):
        self.env = env
        self.stations = stations
        self.junctions = junctions
        self._scenarios: List[Dict] = make_scenarios(env, stations, train_infos=None)

        self.active_index: Optional[int] = None
        self.timetable: Optional[Timetable] = None
        self.train_infos: Dict = {}
        self.priorities: Dict = {}
        self.last_result: Optional[ResolutionResult] = None

        self.active_enable_delays: bool = False
        self.active_delay_probability: float = 0.15

    # ── Public API ─────────────────────────────────────────────────────────

    def list_scenarios(self) -> List[ScenarioInfo]:
        return [
            ScenarioInfo(
                index=i,
                name=s['name'],
                description=s.get('description', ''),
                n_trains=len(s['timetable'].schedules),
                enable_random_delays=s.get('enable_random_delays', False),
            )
            for i, s in enumerate(self._scenarios)
        ]

    def load_scenario(self, idx: int) -> Tuple[Timetable, Dict, Dict, ResolutionResult]:
        """Full load: deep-copy, env reset, resolve. Used for fresh scenario start."""
        scenario, timetable, train_infos, priorities = self._load_scenario_base(idx)

        result = resolve_all_conflicts_safe(
            self.env, timetable, priorities, train_infos,
            max_iterations=200, verbose=False,
            stagger_spawn=scenario.get('stagger_spawn', False),
            rejected_resolutions=scenario.get('rejected_resolutions', None),
        )

        # Apply learned resolutions AFTER the resolver so they always take
        # priority. Pre-applying before the resolver fails because
        # ConflictDetector.project_train_positions ignores hold_until, so
        # the detector still sees the conflict and overwrites the learned choice.
        self._override_with_learned(idx, timetable)

        self.last_result = result
        return timetable, train_infos, priorities, result

    def load_scenario_manual(self, idx: int) -> Tuple[Timetable, Dict, Dict]:
        """
        Load scenario WITHOUT running the conflict resolver.
        Used in manual mode so the user resolves conflicts interactively.
        """
        self._load_scenario_base(idx)
        return self.timetable, self.train_infos, self.priorities

    def reload_active(self) -> Tuple[Timetable, Dict, Dict, ResolutionResult]:
        """Re-run the active scenario from scratch (restores cancelled trains)."""
        if self.active_index is None:
            raise RuntimeError("No scenario loaded yet.")
        return self.load_scenario(self.active_index)

    def cancel_train_live(self, train_id: int) -> ResolutionResult:
        """Remove a not-yet-spawned train and re-resolve without env reset."""
        if self.timetable is None:
            raise RuntimeError("No scenario loaded.")
        if train_id not in self.timetable.schedules:
            raise KeyError(f"Train {train_id} not in active timetable.")
        if self.env.agents[train_id].position is not None:
            raise ValueError(f"Train {train_id} is already on the grid — cannot cancel.")

        self.timetable.schedules.pop(train_id, None)
        self.timetable.priorities.pop(train_id, None)
        self.train_infos.pop(train_id, None)
        self.priorities.pop(train_id, None)

        result = resolve_all_conflicts_safe(
            self.env, self.timetable, self.priorities, self.train_infos,
            max_iterations=200, verbose=False, stagger_spawn=False,
        )
        self.last_result = result
        return result

    def get_next_conflict_and_options(self):
        """
        Detect the first unresolved conflict and generate its resolution options
        in a single detector pass (avoids running the detector twice).

        Returns:
            (conflict, options) — conflict is None if timetable is clean.
            options is a list of Resolution objects sorted by delay_added (best first).
        """
        from ConflictResolver import ConflictDetector, ResolutionGenerator
        if self.timetable is None:
            return None, []

        detector = ConflictDetector(self.env, self.timetable)
        conflicts, projections = detector.detect_conflicts(0)

        active = set(self.timetable.schedules.keys())
        conflict = next(
            (c for c in conflicts if c.train_a in active and c.train_b in active),
            None,
        )
        if conflict is None:
            return None, []

        generator = ResolutionGenerator(self.env)
        options = generator.generate_all_options(
            conflict, self.priorities, self.timetable, projections)
        return conflict, sorted(options, key=lambda o: o.delay_added)

    def apply_resolution_option(self, option) -> None:
        """Apply a user-chosen resolution option to the active timetable."""
        from ConflictResolver import ResolutionType
        schedule = self.timetable.get_schedule(option.train_to_delay)
        if schedule is None:
            return
        if option.resolution_type == ResolutionType.REROUTE:
            schedule.route               = option.new_route
            schedule.planned_arrival    += option.delay_added
            schedule.was_rerouted        = True
            schedule.reroute_delay_added += option.delay_added
        elif option.resolution_type == ResolutionType.WAIT:
            schedule.planned_arrival    += option.delay_added
            schedule.was_held            = True
            schedule.hold_until          = option.wait_until
            schedule.hold_at_cell        = option.wait_at_cell
            # WAIT delay is tracked separately from reroute delay so the
            # table can show them independently — do NOT add to reroute_delay_added

    # ── Learned resolution API
    def save_learned_resolution(self, scenario_idx: int, option) -> bool:
        """
        Persist a manually chosen resolution for a scenario.
        Returns True on success, False on failure (prints reason).
        """
        try:
            data = self._load_learned_file()
            key  = str(scenario_idx)
            if key not in data:
                data[key] = []

            entry = {
                'train_to_delay':  int(option.train_to_delay),
                'resolution_type': str(option.resolution_type.value),
                'delay_added':     int(option.delay_added),
                'wait_at_cell':    [int(x) for x in option.wait_at_cell]
                                   if option.wait_at_cell else None,
                'wait_until':      int(option.wait_until)
                                   if option.wait_until is not None else None,
            }
            # Replace any existing entry for this train (don't accumulate duplicates)
            data[key] = [e for e in data[key]
                         if e['train_to_delay'] != option.train_to_delay]
            data[key].append(entry)

            with open(_LEARNED_PATH, 'w') as f:
                import json as _json
                _json.dump(data, f, indent=2)
            print(f"[LEARNED] Saved to {_LEARNED_PATH}")
            return True
        except Exception as e:
            print(f"[LEARNED] Save failed: {e}")
            return False

    def get_learned_resolutions(self, scenario_idx: int) -> List[dict]:
        """Return all stored resolutions for a scenario (empty list if none)."""
        data = self._load_learned_file()
        return data.get(str(scenario_idx), [])

    def has_learned_resolutions(self, scenario_idx: int) -> bool:
        return len(self.get_learned_resolutions(scenario_idx)) > 0

    def clear_learned_resolutions(self, scenario_idx: int) -> None:
        """Delete all stored resolutions for a scenario."""
        data = self._load_learned_file()
        data.pop(str(scenario_idx), None)
        self._save_learned_file(data)

    def _override_with_learned(self, scenario_idx: int, timetable: Timetable) -> None:
        """
        Override resolver choices with stored learned resolutions.

        Called AFTER resolve_all_conflicts_safe so the learned resolution
        always takes priority. Resets the target train's schedule to its
        base departure timing before applying, so there is no double-counting
        of delays.
        """
        from ConflictResolver import ResolutionType
        entries = self.get_learned_resolutions(scenario_idx)
        if not entries:
            return

        # Get base (pre-resolve) schedules to reset from
        base_scenario = self._scenarios[scenario_idx]
        base_timetable = deepcopy(base_scenario['timetable'])

        for entry in entries:
            tid   = entry['train_to_delay']
            sched = timetable.schedules.get(tid)
            base  = base_timetable.schedules.get(tid)
            if sched is None or base is None:
                continue

            rtype = entry['resolution_type']
            if rtype == ResolutionType.WAIT.value:
                # Reset to base arrival, then apply learned delay cleanly
                sched.planned_arrival          = base.planned_arrival + entry['delay_added']
                sched.original_planned_arrival = base.planned_arrival + entry['delay_added']
                sched.reroute_delay_added      = entry['delay_added']
                sched.was_held                 = True
                sched.was_rerouted             = False
                sched.hold_until               = entry.get('wait_until')
                cell = entry.get('wait_at_cell')
                sched.hold_at_cell             = tuple(cell) if cell else None
                sched.route                    = list(base.route)  # restore original route

    def _apply_learned_resolutions(self, scenario_idx: int, timetable: Timetable) -> None:
        """
        Apply stored resolutions to the timetable.
        Used in manual mode to pre-select the learned option in the UI.
        NOT used during auto load (use _override_with_learned instead).
        """
        from ConflictResolver import ResolutionType
        entries = self.get_learned_resolutions(scenario_idx)
        for entry in entries:
            tid   = entry['train_to_delay']
            rtype = entry['resolution_type']
            sched = timetable.schedules.get(tid)
            if sched is None:
                continue
            if rtype == ResolutionType.WAIT.value:
                sched.planned_arrival    += entry['delay_added']
                sched.was_held            = True
                sched.hold_until          = entry.get('wait_until')
                cell = entry.get('wait_at_cell')
                sched.hold_at_cell        = tuple(cell) if cell else None
                sched.reroute_delay_added += entry['delay_added']

    def _load_learned_file(self) -> dict:
        try:
            with open(_LEARNED_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_learned_file(self, data: dict) -> None:
        try:
            with open(_LEARNED_PATH, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def turnback_train(self, train_id: int, new_target: tuple,
                       current_step: int = 0) -> ResolutionResult:
        """
        Reroute a running train to a new target city.

        new_target is the station cluster position from the dialog.
        We try nearby terminal cells to find one with a valid BFS route
        from the train's current position.
        """
        from Corridor_environment import compute_route_bfs

        if self.timetable is None:
            raise RuntimeError("No scenario loaded.")
        if train_id not in self.timetable.schedules:
            raise KeyError(f"Train {train_id} not in timetable.")

        agent = self.env.agents[train_id]
        if agent.position is None:
            raise ValueError(f"Train {train_id} is not on the grid yet.")

        curr_pos = tuple(agent.position)
        curr_dir = int(agent.direction)

        # Collect all actual terminal cells used by agents (initial_positions + targets)
        terminal_cells = set()
        for a in self.env.agents:
            if a.initial_position is not None:
                terminal_cells.add(tuple(a.initial_position))
            if a.target is not None:
                terminal_cells.add(tuple(a.target))

        # Sort candidates by distance to the requested station position
        candidates = sorted(terminal_cells,
                            key=lambda c: abs(c[0]-new_target[0]) + abs(c[1]-new_target[1]))

        # Find the closest candidate that has a valid BFS route
        new_route   = None
        actual_target = None
        for candidate in candidates:
            if candidate == curr_pos:
                continue
            route = compute_route_bfs(
                self.env, curr_pos, candidate,
                use_transitions=True, start_direction=curr_dir,
            ) or compute_route_bfs(
                self.env, curr_pos, candidate, use_transitions=True)
            if route:
                new_route     = route
                actual_target = candidate
                break

        if not new_route:
            raise LookupError(
                f"No valid route from {curr_pos} to any terminal near {new_target}.")

        # Update flatland agent target
        agent.target = actual_target

        # Rebuild every on-grid train's schedule from its current position
        for tid, sched in self.timetable.schedules.items():
            a = self.env.agents[tid]

            sched.was_held            = False
            sched.hold_at_cell        = None
            sched.hold_until          = None
            sched.reroute_delay_added = 0
            sched.was_rerouted        = (tid == train_id)
            sched.actual_arrival      = None

            if a.position is not None:
                if tid == train_id:
                    route = new_route
                else:
                    pos = tuple(a.position)
                    d   = int(a.direction)
                    route = compute_route_bfs(
                        self.env, pos, tuple(a.target),
                        use_transitions=True, start_direction=d,
                    ) or compute_route_bfs(
                        self.env, pos, tuple(a.target),
                        use_transitions=True,
                    ) or sched.route

                sched.route                    = route
                sched.planned_departure        = current_step
                sched.planned_arrival          = current_step + len(route)
                sched.original_planned_arrival = sched.planned_arrival

        self._sync_env_departures(self.timetable)

        result = resolve_all_conflicts_safe(
            self.env, self.timetable, self.priorities, self.train_infos,
            max_iterations=200, verbose=False, stagger_spawn=False,
        )

        self._fix_rerouted_routes_after_turnback(current_step)
        self._fix_blocking_holds(train_id, current_step)

        self._fix_blocking_holds(train_id, current_step)

        self.last_result = result
        return result

    def _fix_rerouted_routes_after_turnback(self, current_step: int):

        from Corridor_environment import compute_route_bfs

        for tid, sched in self.timetable.schedules.items():
            agent = self.env.agents[tid]
            if agent.position is None:
                continue  # unspawned — skip

            curr_pos = tuple(agent.position)

            # Check if route[0] matches current position
            if sched.route and tuple(sched.route[0]) == curr_pos:
                continue  # already correct

            # Route doesn't start at current position — recompute
            d     = int(agent.direction)
            route = compute_route_bfs(
                self.env, curr_pos, tuple(agent.target),
                use_transitions=True, start_direction=d,
            ) or compute_route_bfs(
                self.env, curr_pos, tuple(agent.target),
                use_transitions=True,
            )
            if route:
                sched.route                    = route
                sched.planned_departure        = current_step
                sched.planned_arrival          = current_step + len(route)
                sched.original_planned_arrival = sched.planned_arrival

    def _fix_blocking_holds(self, turned_train_id: int, current_step: int):
        sched = self.timetable.schedules.get(turned_train_id)
        if sched is None or not sched.was_held or sched.hold_at_cell is None:
            return

        hold_cell  = sched.hold_at_cell
        hold_until = sched.hold_until or (current_step + sched.reroute_delay_added)

        # Check if any other active train's route passes through the hold cell
        # during the hold window
        from Corridor_environment import compute_route_bfs
        blocking = False
        max_clear_step = hold_until

        for tid, other in self.timetable.schedules.items():
            if tid == turned_train_id:
                continue
            agent = self.env.agents[tid]
            if agent.position is None:
                continue  # unspawned — can't conflict now
            # Check if hold_cell appears in remaining route
            try:
                route_cells = [tuple(c) for c in other.route]
                if tuple(hold_cell) in route_cells:
                    blocking = True
                    # Estimate when the other train passes the hold cell:
                    # it's at route_cells[0] now, moves 1 cell/step
                    idx = route_cells.index(tuple(hold_cell))
                    clear_at = current_step + idx + 5   # +5 buffer
                    max_clear_step = max(max_clear_step, clear_at)
            except Exception:
                continue

        if blocking:
            # Replace hold-at-cell with a simple pre-departure delay:
            # train waits at its current position until all other trains clear
            delay = max_clear_step - current_step
            sched.was_held            = True
            sched.hold_at_cell        = tuple(self.env.agents[turned_train_id].position)
            sched.hold_until          = current_step + delay
            sched.planned_departure   = current_step + delay
            sched.planned_arrival     = sched.planned_departure + len(sched.route)
            sched.original_planned_arrival = sched.planned_arrival
            sched.reroute_delay_added = delay

    def active_info(self) -> Optional[ScenarioInfo]:
        if self.active_index is None:
            return None
        return self.list_scenarios()[self.active_index]

    # ── Internal helpers ───────────────────────────────────────────────────

    def _load_scenario_base(self, idx: int):
        """
        Shared setup for load_scenario and load_scenario_manual.
        Deep-copies scenario data, resets env, syncs departures, and sets
        all active_* attributes. Returns (scenario_dict, timetable, train_infos, priorities).
        """
        if idx < 0 or idx >= len(self._scenarios):
            raise IndexError(
                f"Scenario index {idx} out of range (0–{len(self._scenarios)-1})")

        scenario    = self._scenarios[idx]
        timetable   = deepcopy(scenario['timetable'])
        train_infos = deepcopy(scenario['train_infos'])
        priorities  = deepcopy(scenario['priorities'])

        self.env.reset()
        self._sync_env_departures(timetable)

        self.active_index             = idx
        self.timetable                = timetable
        self.train_infos              = train_infos
        self.priorities               = priorities
        self.last_result              = None
        self.active_enable_delays     = scenario.get('enable_random_delays', False)
        self.active_delay_probability = scenario.get('delay_probability', 0.15)

        return scenario, timetable, train_infos, priorities

    def _sync_env_departures(self, timetable: Timetable):
        for agent_id in range(len(self.env.agents)):
            agent    = self.env.agents[agent_id]
            schedule = timetable.schedules.get(agent_id)
            dep = schedule.planned_departure if schedule else 9999
            if hasattr(agent, 'earliest_departure'):
                agent.earliest_departure = dep
            if hasattr(self.env, 'timetable') and self.env.timetable is not None:
                try:
                    self.env.timetable.earliest_departures[agent_id][0] = dep
                except Exception:
                    pass