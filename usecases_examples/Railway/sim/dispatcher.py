"""
TimetableDispatcher - drives each train along its timetable route in Flatland.

Per step: confirm last moves, compute each train's next move, let the
higher-priority train win when two want the same cell, stop trains whose
next cell is occupied. Holds and scripted actions of the experiment
scenarios are applied on top of these actions by the ScenarioPlayer.

Removed against the old version (not used by the scripted scenarios):
random delay injection, timetable holds (hold_at_cell / hold_until),
mid-run re-planning (_init_routes(preserve_active)), TrainInfo updates,
print reports.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from flatland.core.grid.grid4_utils import get_new_position
from flatland.envs.rail_generators import RailEnvTransitions

# Flatland RailEnvActions
DO_NOTHING, MOVE_LEFT, MOVE_FORWARD, MOVE_RIGHT, STOP_MOVING = 0, 1, 2, 3, 4

DELTA_TO_DIR: Dict[Tuple[int, int], int] = {(-1, 0): 0, (0, 1): 1, (1, 0): 2, (0, -1): 3}


def dir_to_action(current_dir: int, target_dir: int) -> int:
    diff = (target_dir - current_dir) % 4
    if diff == 1:
        return MOVE_RIGHT
    if diff == 3:
        return MOVE_LEFT
    return MOVE_FORWARD


def route_to_directions(route: List[Tuple[int, int]]) -> List[int]:
    dirs = []
    for a, b in zip(route, route[1:]):
        d = DELTA_TO_DIR.get((b[0] - a[0], b[1] - a[1]))
        if d is None:
            raise ValueError(f"Non-adjacent cells: {a} -> {b}")
        dirs.append(d)
    return dirs


@dataclass
class DispatchEvent:
    step: int
    event_type: str      # departed, arrived, blocked, spawn_blocked, priority_yield, off_route, deadlock_warning
    agent_id: int
    position: Optional[Tuple[int, int]] = None
    detail: str = ""

    def __str__(self):
        pos = f" at {self.position}" if self.position else ""
        return f"Step {self.step:3d} | Train {self.agent_id} | {self.event_type:16s}{pos} | {self.detail}"


@dataclass
class AgentExecState:
    agent_id: int
    route_idx: int = 0
    steps_blocked: int = 0
    departed: bool = False
    arrived: bool = False
    off_route: bool = False


DEADLOCK_THRESHOLD = 25   # steps blocked before a deadlock_warning event


class TimetableDispatcher:
    """Executes a Timetable in Flatland with blocking awareness."""

    def __init__(self, env, timetable):
        self.env = env
        self.timetable = timetable
        self.rail_trans = RailEnvTransitions()
        self._directions: Dict[int, List[int]] = {}
        self._exec: Dict[int, AgentExecState] = {}
        self._step_events: List[DispatchEvent] = []
        for agent_id, schedule in timetable.schedules.items():
            try:
                self._directions[agent_id] = (route_to_directions(schedule.route)
                                              if len(schedule.route) >= 2 else [])
            except ValueError as e:
                print(f"[dispatcher] WARNING train {agent_id}: {e}")
                self._directions[agent_id] = []
            self._exec[agent_id] = AgentExecState(agent_id=agent_id)

    def get_step_events(self) -> List[DispatchEvent]:
        """Events of the last get_actions() + record_arrivals() call."""
        return list(self._step_events)

    # ── per step ──────────────────────────────────────────────────────────

    def get_actions(self, step: int) -> Dict[int, int]:
        """Actions for env.step() at this step. Call record_arrivals(step) after env.step()."""
        self._step_events = []
        n = self.env.get_num_agents()

        for agent_id in range(n):                       # 1: confirm moves of last step
            self._confirm_move(agent_id, step)

        intentions: Dict[int, Tuple[Tuple[int, int], int]] = {}
        for agent_id in range(n):                       # 2a: intentions
            result = self._compute_intention(agent_id, step)
            if result is not None:
                intentions[agent_id] = result

        cell_to_movers: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for agent_id, (next_cell, action) in intentions.items():   # 2b: same target cell
            if action in (MOVE_LEFT, MOVE_FORWARD, MOVE_RIGHT):
                cell_to_movers[next_cell].append(agent_id)
        losers: Set[int] = set()
        for cell, movers in cell_to_movers.items():
            if len(movers) > 1:
                movers.sort(key=self.timetable.get_priority, reverse=True)
                for loser in movers[1:]:
                    losers.add(loser)
                    self._step_events.append(DispatchEvent(
                        step, "priority_yield", loser, cell, f"yield to Train {movers[0]}"))

        actions: Dict[int, int] = {}                    # 2c: final actions
        for agent_id in range(n):
            if agent_id not in self._exec:
                actions[agent_id] = DO_NOTHING          # not in the timetable
                continue
            state = self._exec[agent_id]
            agent = self.env.agents[agent_id]
            if agent_id in losers:
                actions[agent_id] = STOP_MOVING
                state.steps_blocked += 1
            elif agent_id in intentions:
                action = intentions[agent_id][1]
                actions[agent_id] = action
                if action in (MOVE_LEFT, MOVE_FORWARD, MOVE_RIGHT):
                    state.steps_blocked = 0
                else:
                    state.steps_blocked += 1
            else:
                # Off grid: DO_NOTHING. On grid: must STOP_MOVING explicitly,
                # otherwise Flatland keeps moving the train.
                actions[agent_id] = DO_NOTHING if agent.position is None else STOP_MOVING

            if state.steps_blocked >= DEADLOCK_THRESHOLD and not state.arrived:
                self._step_events.append(DispatchEvent(
                    step, "deadlock_warning", agent_id,
                    tuple(agent.position) if agent.position is not None else None,
                    f"blocked {state.steps_blocked} steps"))
        return actions

    def record_arrivals(self, step: int):
        """
        Call right after env.step(actions) of this step.
        Bugfix K32: arrival used to be detected at the next get_actions()
        call, so it was one step late and never recorded for the last train
        (the run stops when all trains are done).
        """
        for agent_id, state in self._exec.items():
            agent = self.env.agents[agent_id]
            if state.arrived or "DONE" not in agent.state.name:
                continue
            state.arrived = True
            schedule = self.timetable.schedules[agent_id]
            schedule.actual_arrival = step
            delay = schedule.arrival_delay
            self._step_events.append(DispatchEvent(
                step, "arrived", agent_id, None,
                f"actual={step} planned={schedule.planned_arrival} "
                f"delay={'+' + str(delay) if delay else 'on time'}"))

    # ── internals ─────────────────────────────────────────────────────────

    def _confirm_move(self, agent_id: int, step: int):
        """Advance route_idx only when the train is provably at route[idx + 1]."""
        if agent_id not in self._exec:
            return
        agent = self.env.agents[agent_id]
        route = self.timetable.schedules[agent_id].route
        if agent.position is None or not route:
            return
        state = self._exec[agent_id]
        pos, idx = tuple(agent.position), state.route_idx
        if idx < len(route) and tuple(route[idx]) == pos:
            return
        if idx + 1 < len(route) and tuple(route[idx + 1]) == pos:
            state.route_idx += 1
            state.off_route = False
            return
        if not state.off_route:
            state.off_route = True
            # old code logged this with step=0 (K31 part 2)
            self._step_events.append(DispatchEvent(
                step, "off_route", agent_id, pos,
                f"expected {tuple(route[min(idx, len(route) - 1)])} "
                f"or {tuple(route[min(idx + 1, len(route) - 1)])}"))

    def _compute_intention(self, agent_id: int, step: int) -> Optional[Tuple[Tuple[int, int], int]]:
        if agent_id not in self._exec:
            return None
        schedule = self.timetable.schedules[agent_id]
        agent = self.env.agents[agent_id]
        state = self._exec[agent_id]

        if "DONE" in agent.state.name or step < schedule.planned_departure:
            return None

        if agent.position is None:                      # not yet on the grid
            if not schedule.route:
                return None
            entry = tuple(schedule.route[0])
            if self._is_occupied(entry, exclude=agent_id):
                state.steps_blocked += 1
                self._step_events.append(DispatchEvent(
                    step, "spawn_blocked", agent_id, entry, "entry cell occupied"))
                return (entry, STOP_MOVING)
            if not state.departed:
                state.departed = True
                schedule.actual_departure = step
                self._step_events.append(DispatchEvent(
                    step, "departed", agent_id, entry,
                    f"planned={schedule.planned_departure} actual={step}"))
            return (entry, MOVE_FORWARD)

        directions = self._directions.get(agent_id, [])
        idx = state.route_idx
        # K31: the old code set arrived=True here without actual_arrival.
        # Arrival is now only recorded from Flatland's DONE state.
        if not directions or idx >= len(directions):
            return None
        if state.off_route:
            state.steps_blocked += 1
            return None

        next_dir = directions[idx]
        cell_val = self.env.rail.grid[agent.position[0], agent.position[1]]
        valid_exits = self.rail_trans.get_transitions(cell_val, agent.direction)
        if not valid_exits[next_dir]:
            best = self._pick_best_exit(directions, idx, valid_exits)
            if best is None:
                return None
            next_dir = best
        next_cell = tuple(get_new_position(agent.position, next_dir))

        if self._is_occupied(next_cell, exclude=agent_id):
            state.steps_blocked += 1
            self._step_events.append(DispatchEvent(
                step, "blocked", agent_id, next_cell, "next cell occupied"))
            return (next_cell, STOP_MOVING)
        return (next_cell, dir_to_action(agent.direction, next_dir))

    def _is_occupied(self, cell: Tuple[int, int], exclude: int) -> bool:
        return any(i != exclude and a.position is not None and tuple(a.position) == cell
                   for i, a in enumerate(self.env.agents))

    @staticmethod
    def _pick_best_exit(directions: List[int], idx: int, valid_exits) -> Optional[int]:
        valid = [d for d in range(4) if valid_exits[d]]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]
        for intended in directions[idx:]:
            if intended in valid:
                return intended
        return valid[0]
