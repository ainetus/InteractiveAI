"""
TimetableDispatcher - Real-time dispatcher bridging offline planning and Flatland execution.
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
from flatland.core.grid.grid4_utils import get_new_position
from flatland.envs.rail_generators import RailEnvTransitions


DELTA_TO_DIR: Dict[Tuple[int, int], int] = {
    (-1,  0): 0,
    ( 0,  1): 1,
    ( 1,  0): 2,
    ( 0, -1): 3,
}

def dir_to_action(current_dir: int, target_dir: int) -> int:
    diff = (target_dir - current_dir) % 4
    if diff == 0:   return 2
    elif diff == 1: return 3
    elif diff == 3: return 1
    else:           return 2


def route_to_directions(route: List[Tuple[int, int]]) -> List[int]:
    dirs = []
    for i in range(len(route) - 1):
        dr = route[i+1][0] - route[i][0]
        dc = route[i+1][1] - route[i][1]
        d = DELTA_TO_DIR.get((dr, dc))
        if d is None:
            raise ValueError(f"Non-adjacent cells: {route[i]} -> {route[i+1]}")
        dirs.append(d)
    return dirs


@dataclass
class DispatchEvent:
    step: int
    event_type: str
    agent_id: int
    position: Optional[Tuple[int, int]] = None
    detail: str = ""

    def __str__(self):
        pos = f" at {self.position}" if self.position else ""
        return (f"Step {self.step:3d} | Train {self.agent_id} | "
                f"{self.event_type:20s}{pos} | {self.detail}")


@dataclass
class AgentExecState:
    agent_id: int
    route_idx: int = 0
    steps_blocked: int = 0
    departed: bool = False
    arrived: bool = False
    off_route: bool = False
    DEADLOCK_THRESHOLD: int = 25


class TimetableDispatcher:
    """
    Executes a resolved Timetable in Flatland with real-time blocking awareness.
    """

    def __init__(self, env, timetable, ignore_holds: bool = False,
                 train_infos: Dict = None,
                 enable_random_delays: bool = False,
                 delay_probability: float = 0.15,
                 delay_min_steps: int = 5,
                 delay_max_steps: int = 30,
                 random_seed: int = None):
        """
        Args:
            ignore_holds:         Skip planned hold/wait instructions.
            train_infos:          Dict of train_id -> TrainInfo. When provided,
                                  actual_arrival updates current_delay for live
                                  priority recalculation.
            enable_random_delays: If True, randomly inject delays during simulation.
            delay_probability:    Probability that any given train will experience
                                  one delay event during its journey (default 0.15 = 15%).
                                  Roll happens once when a train first moves, not every step.
            delay_min_steps:      Minimum injected delay duration in steps.
            delay_max_steps:      Maximum injected delay duration in steps.
            random_seed:          Seed for reproducible random delays.
        """
        self.env = env
        self.timetable = timetable
        self.ignore_holds = ignore_holds
        self._train_infos = train_infos or {}

        # Random delay injection config
        self.enable_random_delays = enable_random_delays
        self.delay_probability = delay_probability
        self.delay_min_steps = delay_min_steps
        self.delay_max_steps = delay_max_steps

        import random
        self._rng = random.Random(random_seed)

        # Set when an injection fires this step — caller checks this to trigger re-plan
        self._replan_needed: bool = False
        self._injection_log: List[dict] = []  # full history of injections
        # Tracks trains for which the "will this train get a delay?" decision
        # has already been made. Maps train_id -> (will_be_delayed, at_step)
        self._delay_decided: Dict[int, tuple] = {}

        self.rail_trans = RailEnvTransitions()
        self._directions: Dict[int, List[int]] = {}
        self._exec: Dict[int, AgentExecState] = {}
        self._step_events: List[DispatchEvent] = []
        self._init_routes()

    def _init_routes(self, preserve_active: bool = False):
        """
        Pre-compute direction sequences from position routes.

        Args:
            preserve_active: If True, preserve route_idx and exec state for
                             agents already on the grid (mid-journey re-plan).
                             Only recompute directions; don't reset progress.
                             New/unstarted agents are initialised normally.
        """
        for agent_id, schedule in self.timetable.schedules.items():
            route = schedule.route
            if route and len(route) >= 2:
                try:
                    self._directions[agent_id] = route_to_directions(route)
                except ValueError as e:
                    print(f"  [Dispatcher] Warning agent {agent_id}: {e}")
                    self._directions[agent_id] = []
            else:
                self._directions[agent_id] = []

            agent = self.env.agents[agent_id]
            already_active = (agent.position is not None
                              or (agent_id in self._exec
                                  and self._exec[agent_id].departed))

            if preserve_active and already_active and agent_id in self._exec:
                # Keep existing exec state — only sync route_idx to current position
                state = self._exec[agent_id]
                if agent.position is not None and route:
                    current_pos = tuple(agent.position)
                    # Find where the agent currently is in the new route
                    best_idx = 0
                    best_dist = float('inf')
                    for i, cell in enumerate(route):
                        dist = abs(cell[0]-current_pos[0]) + abs(cell[1]-current_pos[1])
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = i
                    state.route_idx = best_idx
                    state.off_route = False  # clear off-route flag after re-plan
                    state.steps_blocked = 0
            else:
                # Fresh init for agents not yet started
                self._exec[agent_id] = AgentExecState(agent_id=agent_id)

    def reset(self):
        for state in self._exec.values():
            state.route_idx = 0
            state.steps_blocked = 0
            state.departed = False
            state.arrived = False
            state.off_route = False
        self._step_events = []
        self._replan_needed = False
        self._injection_log = []
        self._delay_decided = {}

    def get_pending_replan(self) -> bool:
        """
        Returns True if a delay was injected this step that requires
        the caller to re-run the conflict resolver.

        The caller is responsible for re-planning — the dispatcher does
        not do this itself to keep concerns separated.

        Call once per step after get_actions(). Resets automatically
        on the next get_actions() call.
        """
        return self._replan_needed

    def get_injection_log(self) -> List[dict]:
        """
        Return full history of injected delays.

        Each entry: {step, train_id, delay_steps, position}
        """
        return list(self._injection_log)

    def get_step_events(self) -> List[DispatchEvent]:
        return list(self._step_events)

    def get_actions(self, step: int) -> Dict[int, int]:
        self._step_events = []
        self._replan_needed = False  # reset each step

        # Inject random delays before computing actions
        if self.enable_random_delays:
            self._maybe_inject_delays(step)

        # Pass 1: confirm moves from last step
        for agent_id in range(self.env.get_num_agents()):
            self._confirm_move(agent_id)

        # Pass 2a: compute intentions
        intentions: Dict[int, Tuple[Tuple[int, int], int]] = {}
        for agent_id in range(self.env.get_num_agents()):
            result = self._compute_intention(agent_id, step)
            if result is not None:
                intentions[agent_id] = result

        # Pass 2b: resolve simultaneous movement conflicts by priority
        cell_to_movers: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for agent_id, (next_cell, action) in intentions.items():
            if action in (1, 2, 3):
                cell_to_movers[next_cell].append(agent_id)

        priority_losers: Set[int] = set()
        for cell, movers in cell_to_movers.items():
            if len(movers) > 1:
                movers.sort(key=lambda a: self.timetable.get_priority(a), reverse=True)
                for loser in movers[1:]:
                    priority_losers.add(loser)
                    self._step_events.append(DispatchEvent(
                        step=step, event_type='priority_yield',
                        agent_id=loser, position=cell,
                        detail=(f"yield to Train {movers[0]} "
                                f"(pri {self.timetable.get_priority(movers[0]):.1f}"
                                f" >= {self.timetable.get_priority(loser):.1f})")
                    ))

        # Pass 2c: build final actions
        actions: Dict[int, int] = {}
        for agent_id in range(self.env.get_num_agents()):
            if agent_id not in self._exec:
                actions[agent_id] = 0  # not in this scenario's timetable
                continue
            state = self._exec[agent_id]
            agent = self.env.agents[agent_id]

            if agent_id in priority_losers:
                actions[agent_id] = 4
                state.steps_blocked += 1
            elif agent_id in intentions:
                _, action = intentions[agent_id]
                actions[agent_id] = action
                if action in (1, 2, 3):
                    state.steps_blocked = 0
                else:
                    state.steps_blocked += 1
            else:
                # No intention = hold/wait this step.
                # action=0 ("do nothing") is only correct for agents not yet
                # on the grid. For active agents already on the grid, we must
                # send action=4 (STOP_MOVING) otherwise flatland may continue
                # moving the agent in its current direction.
                if agent.position is None:
                    actions[agent_id] = 0   # not spawned yet — correct
                else:
                    actions[agent_id] = 4   # active on grid — must explicitly stop

            if state.steps_blocked >= state.DEADLOCK_THRESHOLD and not state.arrived:
                self._step_events.append(DispatchEvent(
                    step=step, event_type='deadlock_warning',
                    agent_id=agent_id,
                    position=(tuple(agent.position) if agent.position else None),
                    detail=f"blocked {state.steps_blocked} steps"
                ))

        return actions

    def _maybe_inject_delays(self, step: int):
        """
        Randomly inject ONE delay event per train during its journey.

        Probability model: when a train first starts moving, roll once to
        decide whether it will experience a delay (delay_probability chance).
        If yes, pick a random step during its remaining journey to apply it.
        This gives each train a ~15% chance of ONE delay event total,
        not a 15% chance every step.

        Rules:
        - Decision made once at first movement (not every step)
        - At most one injection per train per journey
        - Already-under-delay trains are skipped
        - Planned hold_until is shifted forward if injection overlaps it
        """
        for agent_id, schedule in self.timetable.schedules.items():
            agent = self.env.agents[agent_id]
            state = self._exec.get(agent_id)

            if state is None or state.arrived or state.off_route:
                continue
            if agent.position is None:
                continue  # not yet on grid
            if schedule._inject_hold_until > step:
                continue  # already under injected delay
            if schedule.injected_delay_steps > 0:
                continue  # already had a delay this journey

            # Make the once-per-journey decision when train first appears on grid
            if agent_id not in self._delay_decided:
                will_delay = self._rng.random() < self.delay_probability
                if will_delay:
                    # Pick a random step in the remaining route to trigger delay
                    route_remaining = len(schedule.route) - state.route_idx
                    trigger_offset = self._rng.randint(
                        max(1, route_remaining // 4),
                        max(2, route_remaining * 3 // 4)
                    )
                    trigger_step = step + trigger_offset
                else:
                    trigger_step = None
                self._delay_decided[agent_id] = (will_delay, trigger_step)

            will_delay, trigger_step = self._delay_decided[agent_id]
            if not will_delay or trigger_step is None:
                continue
            if step < trigger_step:
                continue  # not yet time to inject

            delay = self._rng.randint(self.delay_min_steps, self.delay_max_steps)
            schedule._inject_hold_until = step + delay
            schedule.injected_delay_steps += delay

            # If train has a planned hold, shift it forward too
            if (getattr(schedule, 'was_held', False)
                    and schedule.hold_until is not None
                    and schedule.hold_until > step):
                schedule.hold_until += delay

            self._replan_needed = True

            entry = {
                'step': step,
                'train_id': agent_id,
                'delay_steps': delay,
                'position': tuple(agent.position),
                'hold_until': step + delay,
            }
            self._injection_log.append(entry)

            name = (self._train_infos[agent_id].name
                    if agent_id in self._train_infos else f"Train {agent_id}")
            self._step_events.append(DispatchEvent(
                step=step, event_type='delay_injected',
                agent_id=agent_id,
                position=tuple(agent.position),
                detail=f"{name} held {delay} steps (until step {step + delay})"
            ))

    def _confirm_move(self, agent_id: int):
        """
        CONFIRMATION-BASED route_idx advance.
        Only advance when agent is provably at route[idx+1].
        Never scan the whole route.
        """
        if agent_id not in self._exec:
            return  # agent not in this scenario's timetable
        schedule = self.timetable.schedules.get(agent_id)
        agent = self.env.agents[agent_id]
        state = self._exec[agent_id]
        if not schedule or agent.position is None:
            return
        route = schedule.route
        if not route:
            return
        current_pos = tuple(agent.position)
        idx = state.route_idx

        if idx < len(route) and tuple(route[idx]) == current_pos:
            return  # still at expected position, no advance

        if idx + 1 < len(route) and tuple(route[idx + 1]) == current_pos:
            state.route_idx += 1
            state.off_route = False
            return  # confirmed move to next cell

        # Agent is at neither expected position — went off-route
        if not state.off_route:
            state.off_route = True
            self._step_events.append(DispatchEvent(
                step=0, event_type='off_route',
                agent_id=agent_id, position=current_pos,
                detail=(f"expected {tuple(route[min(idx, len(route)-1)])} "
                        f"or {tuple(route[min(idx+1, len(route)-1)])}")
            ))

    def _compute_intention(self, agent_id: int, step: int) -> Optional[Tuple[Tuple[int, int], int]]:
        if agent_id not in self._exec:
            return None  # agent not in this scenario's timetable
        schedule = self.timetable.schedules.get(agent_id)
        if schedule is None:
            return None
        agent = self.env.agents[agent_id]
        state = self._exec[agent_id]
        state_name = agent.state.name if hasattr(agent.state, 'name') else str(agent.state)

        if 'DONE' in state_name:
            if not state.arrived:
                state.arrived = True
                schedule.actual_arrival = step
                # Update current_delay in TrainInfo for live priority recalc
                info = self._train_infos.get(agent_id)
                if info and schedule.arrival_delay is not None:
                    info.current_delay = schedule.arrival_delay
                delay_str = f"+{schedule.arrival_delay}" if schedule.arrival_delay else "on time"
                self._step_events.append(DispatchEvent(
                    step=step, event_type='arrived',
                    agent_id=agent_id,
                    detail=f"actual={step} planned={schedule.original_planned_arrival} delay={delay_str}"))
            return None

        if step < schedule.planned_departure:
            return None

        # Injected delay hold: freeze train regardless of other logic
        if schedule._inject_hold_until > step:
            return (tuple(agent.position), 4) if agent.position else None

        # Hold logic:
        # - hold_at_cell set: move normally until reaching that cell, then
        #   stop there until hold_until. Enables strategic waiting at junctions.
        # - hold_at_cell None: pre-departure delay, stop all movement.
        if (not self.ignore_holds
                and getattr(schedule, 'was_held', False)
                and getattr(schedule, 'hold_until', None)):
            hold_cell = getattr(schedule, 'hold_at_cell', None)
            if hold_cell is None:
                if step < schedule.hold_until:
                    return None
            elif (agent.position is not None
                  and tuple(agent.position) == tuple(hold_cell)
                  and step < schedule.hold_until):
                self._step_events.append(DispatchEvent(
                    step=step, event_type='holding_at_cell',
                    agent_id=agent_id,
                    position=tuple(agent.position),
                    detail=f"waiting until step {schedule.hold_until}"
                ))
                return None
            # else: keep moving toward hold_at_cell

        # Not yet on grid
        if agent.position is None:
            route = schedule.route
            if not route:
                return None
            entry_cell = tuple(route[0])
            if self._is_occupied(entry_cell, exclude=agent_id):
                state.steps_blocked += 1
                self._step_events.append(DispatchEvent(
                    step=step, event_type='spawn_blocked',
                    agent_id=agent_id, position=entry_cell,
                    detail="entry cell occupied"))
                return (entry_cell, 4)
            if not state.departed:
                state.departed = True
                schedule.actual_departure = step
                self._step_events.append(DispatchEvent(
                    step=step, event_type='departed',
                    agent_id=agent_id, position=entry_cell,
                    detail=f"planned={schedule.planned_departure} actual={step}"))
            return (entry_cell, 2)

        # On grid
        directions = self._directions.get(agent_id, [])
        if not directions:
            return None
        idx = state.route_idx
        if idx >= len(directions):
            state.arrived = True
            return None
        if state.off_route:
            state.steps_blocked += 1
            return None

        next_dir = directions[idx]
        next_cell = tuple(get_new_position(agent.position, next_dir))

        # Validate transition
        cell_val = self.env.rail.grid[agent.position[0], agent.position[1]]
        valid_exits = self.rail_trans.get_transitions(cell_val, agent.direction)
        if not valid_exits[next_dir]:
            best = self._pick_best_exit(directions, idx, valid_exits)
            if best is None:
                return None
            next_dir = best
            next_cell = tuple(get_new_position(agent.position, next_dir))

        # Physical blocking
        if self._is_occupied(next_cell, exclude=agent_id):
            state.steps_blocked += 1
            self._step_events.append(DispatchEvent(
                step=step, event_type='blocked',
                agent_id=agent_id, position=next_cell,
                detail="next cell occupied"))
            return (next_cell, 4)

        return (next_cell, dir_to_action(agent.direction, next_dir))

    def _is_occupied(self, cell: Tuple[int, int], exclude: int) -> bool:
        for i, a in enumerate(self.env.agents):
            if i != exclude and a.position is not None:
                if tuple(a.position) == cell:
                    return True
        return False

    def _pick_best_exit(self, directions: List[int], idx: int,
                         valid_exits: Tuple) -> Optional[int]:
        valid_dirs = [d for d in range(4) if valid_exits[d]]
        if not valid_dirs:
            return None
        if len(valid_dirs) == 1:
            return valid_dirs[0]
        for intended in directions[idx:]:
            if intended in valid_dirs:
                return intended
        return valid_dirs[0]

    def print_timetable_plan(self, train_infos: Dict = None):
        """Print goals, plan, and direction compatibility for all trains."""
        DIR_NAMES = {0: "N", 1: "E", 2: "S", 3: "W"}
        print("\n  Timetable plan (train goals + timing + direction check):")
        for agent_id, schedule in sorted(self.timetable.schedules.items()):
            agent = self.env.agents[agent_id]
            target = tuple(agent.target) if agent.target is not None else "?"
            start = tuple(schedule.route[0]) if schedule.route else "?"
            hold_str = (f", hold->step {schedule.hold_until}"
                        if getattr(schedule, 'was_held', False) else "")
            reroute_str = " [REROUTED]" if getattr(schedule, 'was_rerouted', False) else ""
            name = (train_infos[agent_id].name
                    if train_infos and agent_id in train_infos
                    else f"Train {agent_id}")

            # Direction compatibility check
            init_dir = int(agent.initial_direction)
            route_first_dir = None
            dir_ok = "?"
            if schedule.route and len(schedule.route) >= 2:
                try:
                    dirs = route_to_directions(schedule.route)
                    route_first_dir = dirs[0]
                    diff = (route_first_dir - init_dir) % 4
                    if diff == 0:
                        dir_ok = "OK"
                    elif diff == 2:
                        dir_ok = "MISMATCH-180"  # opposite direction = bug
                    else:
                        dir_ok = f"turn({diff*90}deg)"
                except ValueError:
                    dir_ok = "non-adjacent"

            init_str = DIR_NAMES.get(init_dir, str(init_dir))
            first_str = DIR_NAMES.get(route_first_dir, "?") if route_first_dir is not None else "?"

            print(f"    {name}: {start} -> {target} | "
                  f"dep={schedule.planned_departure}{hold_str} | "
                  f"route_len={len(schedule.route)}{reroute_str} | "
                  f"init_dir={init_str} route_dir={first_str} [{dir_ok}]")

    def print_final_report(self, train_infos: Dict = None):
        print("\n" + "=" * 70)
        print(" DISPATCHER EXECUTION REPORT")
        print("=" * 70)
        for agent_id, state in sorted(self._exec.items()):
            agent = self.env.agents[agent_id]
            directions = self._directions.get(agent_id, [])
            pos = tuple(agent.position) if agent.position else "off-grid"
            progress = f"{state.route_idx}/{len(directions)}"
            if state.arrived:
                status = "DONE"
            elif state.off_route:
                status = "OFF-ROUTE"
            elif state.steps_blocked > 10:
                status = f"BLOCKED ({state.steps_blocked} steps)"
            else:
                status = "moving"
            name = (train_infos[agent_id].name
                    if train_infos and agent_id in train_infos
                    else f"Train {agent_id}")
            print(f"  {name}: pos={pos} | progress={progress} | {status}")
        print("=" * 70)