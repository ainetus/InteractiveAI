"""
Conflict Detection and Resolution for train dispatching.

Components:
- ConflictDetector: Projects train positions and finds conflicts
- ResolutionGenerator: Computes alternative routes and wait times
- ConflictResolver: Coordinates detection and resolution

Resolution strategies:
- REROUTE: Send lower-priority train via alternative route
- WAIT: Hold lower-priority train until higher-priority clears

The resolver compares costs and chooses the better option.
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Tuple, Optional, Set
from flatland.core.grid.grid4_utils import get_new_position
from flatland.envs.rail_generators import RailEnvTransitions


class ResolutionType(Enum):
    """Type of resolution for a conflict."""
    REROUTE = "reroute"  # Send train via alternative route
    WAIT = "wait"        # Hold train until path is clear


@dataclass
class Conflict:
    """Represents a detected conflict between two trains."""
    train_a: int
    train_b: int
    cell: Tuple[int, int]
    timestep: int


@dataclass
class Resolution:
    """Represents a resolution for a conflict."""
    resolution_type: ResolutionType
    train_to_delay: int  # Train that gets delayed (rerouted or waits)
    delay_added: int     # Additional timesteps compared to original
    
    # For REROUTE resolutions
    original_route: Optional[List[Tuple[int, int]]] = None
    new_route: Optional[List[Tuple[int, int]]] = None
    
    # For WAIT resolutions
    wait_until: Optional[int] = None  # Timestep when train can proceed
    wait_at_cell: Optional[Tuple[int, int]] = None  # Cell where train waits


# ============== CONFLICT DETECTOR ==============

class ConflictDetector:
    """Detects conflicts by projecting train positions over time."""
    
    def __init__(self, env, timetable):
        self.env = env
        self.timetable = timetable
    
    def project_train_positions(self, train_id, current_step) -> Dict[int, Tuple[int, int]]:
        """
        Project where train will be at each future timestep.
        
        """
        schedule = self.timetable.get_schedule(train_id)
        if schedule is None:
            return {}  # agent not in this scenario's timetable
        agent = self.env.agents[train_id]
        route = schedule.route
        speed = getattr(schedule, 'speed', 1.0)  # 1.0 = normal, 0.5 = 2 steps per cell
        
        if not route:
            return {}
        
        # Check if already done
        state_name = agent.state.name if hasattr(agent.state, 'name') else str(agent.state)
        if 'DONE' in state_name:
            return {}
        
        # Determine starting point and time
        if agent.position is None:
            # Not on grid yet - will start from beginning of route at planned departure
            current_idx = 0
            # Train enters grid at planned_departure + 1 (action taken, then moves)
            start_time = schedule.planned_departure + 1
            
            # Account for hold instruction
            if getattr(schedule, 'was_held', False) and getattr(schedule, 'hold_until', None):
                # Train is held until hold_until, so effective start is later
                start_time = max(start_time, schedule.hold_until + 1)
        else:
            # Already on grid - project from current position
            try:
                current_idx = route.index(agent.position)
            except ValueError:
                # Position not in route - might have been rerouted
                return {}
            start_time = current_step
        
        # Project future positions accounting for speed
        # With speed=0.5, train takes 2 steps per cell
        # Formula: position_index = floor(timestep_offset * speed)
        positions = {}
        remaining_route = route[current_idx:]
        
        # If held, add positions during hold period at first position
        if getattr(schedule, 'was_held', False) and getattr(schedule, 'hold_until', None):
            if agent.position is None:
                hold_pos = route[0]
                for t in range(schedule.planned_departure + 1, schedule.hold_until + 1):
                    positions[t] = hold_pos
        
        if speed >= 1.0:
            # Normal or fast speed - 1 step per cell (fast trains not fully supported yet)
            for i, pos in enumerate(remaining_route):
                positions[start_time + i] = pos
        else:
            # Slow speed - multiple steps per cell
            steps_per_cell = int(1.0 / speed)  # e.g., speed=0.5 → 2 steps per cell
            timestep = start_time
            for pos in remaining_route:
                # Train stays at this position for steps_per_cell timesteps
                for _ in range(steps_per_cell):
                    positions[timestep] = pos
                    timestep += 1
        
        return positions
    
    def detect_conflicts(self, current_step) -> Tuple[List[Conflict], Dict]:
        """
        Find all conflicts between trains.
        
        Detects:
        1. Same cell at same time (standard collision)
        2. Head-on collision (trains swap positions - try to pass through each other)
        
        Args:
            current_step: Current simulation step
            
        Returns:
            Tuple of (List of Conflict objects, projections dict)
        """
        num_agents = self.env.get_num_agents()
        
        # Project all trains
        projections = {}
        for i in range(num_agents):
            projections[i] = self.project_train_positions(i, current_step)
        
        # Find conflicts
        conflicts = []
        for i in range(num_agents):
            for j in range(i + 1, num_agents):
                for step, pos_i in projections[i].items():
                    if step in projections[j]:
                        pos_j = projections[j][step]
                        
                        # Type 1: Same cell at same time
                        if pos_i == pos_j:
                            conflicts.append(Conflict(
                                train_a=i,
                                train_b=j,
                                cell=pos_i,
                                timestep=step,
                            ))
                        
                        # Type 2: Head-on collision (position swap)
                        next_step = step + 1
                        if next_step in projections[i] and next_step in projections[j]:
                            next_pos_i = projections[i][next_step]
                            next_pos_j = projections[j][next_step]
                            
                            # Check if they swap positions (try to pass through each other)
                            if pos_i == next_pos_j and pos_j == next_pos_i:
                                conflicts.append(Conflict(
                                    train_a=i,
                                    train_b=j,
                                    cell=pos_i,  # Report where train_i is (conflict zone)
                                    timestep=step,
                                ))
        
        return conflicts, projections


# ============== RESOLUTION GENERATOR ==============

class ResolutionGenerator:
    """Generates resolution options for conflicts (rerouting)."""
    
    def __init__(self, env):
        self.env = env
        self.rail_trans = RailEnvTransitions()
    
    def compute_route_avoiding_cells(
        self, 
        start: Tuple[int, int], 
        target: Tuple[int, int], 
        blocked_cells: Set[Tuple[int, int]],
        start_direction: Optional[int] = None,
        use_simple_connectivity: bool = False  # Changed default to False
    ) -> List[Tuple[int, int]]:
        """
        Find route avoiding blocked cells using Flatland transitions.
        
        Args:
            start: Starting position
            target: Target position
            blocked_cells: Cells to avoid
            start_direction: Optional starting direction
            use_simple_connectivity: If True, use simple neighbor checking (legacy)
            
        Returns:
            List of positions forming the route, or empty if no route found
        """
        grid = self.env.rail.grid
        height, width = grid.shape
        
        if start == target:
            return [start]
        
        # Direction offsets: N=0, E=1, S=2, W=3
        dir_offsets = [(-1, 0), (0, 1), (1, 0), (0, -1)]
        
        if use_simple_connectivity:
            # Simple mode: just check if neighbor cells have track
            # Only used for custom tracks that don't follow Flatland rules
            queue = deque([(start, [start])])
            visited = {start}
            
            while queue:
                pos, path = queue.popleft()
                
                if pos == target:
                    return path
                
                r, c = pos
                
                for dr, dc in dir_offsets:
                    nr, nc = r + dr, c + dc
                    next_pos = (nr, nc)
                    
                    if (0 <= nr < height and 0 <= nc < width and
                        grid[next_pos] != 0 and
                        next_pos not in visited and
                        next_pos not in blocked_cells):
                        visited.add(next_pos)
                        queue.append((next_pos, path + [next_pos]))
            
            return []  # No path found
        
        # Use Flatland transitions to find valid route
        # First, find all valid routes to target
        all_routes = self._find_all_routes(start, target, max_routes=10, start_direction=start_direction)
        
        # Filter to routes that avoid blocked cells
        valid_routes = []
        for route in all_routes:
            # Check if any cell in route (except start) is blocked
            if not any(cell in blocked_cells for cell in route[1:]):
                valid_routes.append(route)
        
        if not valid_routes:
            return []
        
        # Return shortest valid route
        return min(valid_routes, key=len)
    
    def calculate_wait_cost(
        self,
        train_to_wait: int,
        train_with_priority: int,
        conflict: Conflict,
        timetable,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> Tuple[int, int, Optional[Tuple[int, int]]]:
        """
        Calculate the cost (delay) of waiting for the priority train to pass.
        
        Args:
            train_to_wait: Train that would wait
            train_with_priority: Train that has priority
            conflict: The conflict being resolved
            timetable: Current timetable
            projections: Position projections for all trains
            
        Returns:
            Tuple of (wait_cost, wait_until_timestep, wait_at_cell)
            Returns (infinity, -1, None) if waiting is not possible
        """
        schedule_wait = timetable.get_schedule(train_to_wait)
        schedule_priority = timetable.get_schedule(train_with_priority)
        
        # BOUNDS CHECK: Make sure schedules exist
        if schedule_wait is None or schedule_priority is None:
            return (float('inf'), -1, None)
        
        route_wait = schedule_wait.route
        route_priority = schedule_priority.route
        
        if not route_wait or not route_priority:
            return (float('inf'), -1, None)
        
        # BOUNDS CHECK: Make sure projections exist for both trains
        if train_to_wait not in projections or train_with_priority not in projections:
            return (float('inf'), -1, None)
        
        # Find the conflict zone (overlapping cells)
        overlap = set(route_wait) & set(route_priority)
        if not overlap:
            return (float('inf'), -1, None)
        
        # Find the first overlap cell in the waiting train's route
        # The train should wait BEFORE entering this cell
        first_overlap_idx = None
        for i, cell in enumerate(route_wait):
            if cell in overlap:
                first_overlap_idx = i
                break
        
        if first_overlap_idx is None or first_overlap_idx == 0:
            # Can't wait - already in conflict zone or would start there
            return (float('inf'), -1, None)
        
        # Wait at the cell just before the conflict zone
        wait_at_cell = route_wait[first_overlap_idx - 1]
        
        #
        # Window size = 4 cells (the junction cell + 3 cells ahead).
        # Buffer = 3 extra steps after clear so Train A doesn't tailgate.
        BUFFER_STEPS = 3
        WINDOW_SIZE = 4

        window_cells = set(route_wait[first_overlap_idx:first_overlap_idx + WINDOW_SIZE])

        proj_priority = projections[train_with_priority]

        clear_time = -1
        for timestep, pos in proj_priority.items():
            if pos in window_cells:
                clear_time = max(clear_time, timestep)

        if clear_time == -1:
            # Priority train never enters the window — no conflict, no wait needed
            return (float('inf'), -1, None)

        # Train can proceed after priority train clears the window + buffer
        wait_until = clear_time + BUFFER_STEPS
        
        # Calculate how long the waiting train would need to wait
        # Find when waiting train would reach the conflict entry without waiting
        proj_wait = projections[train_to_wait]
        arrival_at_conflict = None
        for timestep, pos in proj_wait.items():
            if pos == wait_at_cell:
                # This is when train reaches wait cell, next step enters conflict
                arrival_at_conflict = timestep + 1
                break
        
        if arrival_at_conflict is None:
            return (float('inf'), -1, None)
        
        # Wait cost = time spent waiting
        wait_cost = max(0, wait_until - arrival_at_conflict)
        
        return (wait_cost, wait_until, wait_at_cell)
    
    def calculate_reroute_option(
        self,
        train_to_reroute: int,
        train_with_priority: int,
        timetable,
    ) -> Tuple[int, List[Tuple[int, int]], List[Tuple[int, int]]]:
        """
        Calculate the cost (delay) of rerouting.
               
        Returns:
            Tuple of (reroute_cost, original_route, new_route)
            Returns (infinity, [], []) if rerouting is not possible
        """
        schedule_reroute = timetable.get_schedule(train_to_reroute)
        schedule_priority = timetable.get_schedule(train_with_priority)
        
        if schedule_reroute is None:
            return (float('inf'), [], [])
        
        original_route = list(schedule_reroute.route)
        priority_route = list(schedule_priority.route) if schedule_priority else []
        
        # BOUNDS CHECK: Make sure train exists in environment
        if train_to_reroute >= len(self.env.agents):
            return (float('inf'), original_route, [])
        
        # Get departure times
        departure_reroute = schedule_reroute.planned_departure
        departure_priority = schedule_priority.planned_departure if schedule_priority else 0
        
        # Get current state — use actual direction if spawned, initial if not
        agent = self.env.agents[train_to_reroute]
        if agent.position is None:
            start = original_route[0] if original_route else agent.initial_position
            start_direction = int(agent.initial_direction)
        else:
            start = tuple(agent.position)
            start_direction = int(agent.direction)

        target = tuple(agent.target) if hasattr(agent.target, '__iter__') else agent.target

        # Find all possible routes from start to target, respecting direction
        all_routes = self._find_all_routes(start, target, max_routes=5,
                                           start_direction=start_direction)
        
        if not all_routes:
            return (float('inf'), original_route, [])
        
        # Build priority train's temporal occupancy: timestep -> position
        priority_occupancy = {}
        for step_offset, cell in enumerate(priority_route):
            timestep = departure_priority + step_offset
            priority_occupancy[timestep] = cell
        
        original_set = set(original_route)
        
        best_route = None
        best_cost = float('inf')
        
        for route in all_routes:
            # VALIDATION: Route must actually reach the target
            if not route or len(route) < 2:
                continue
            
            if route[-1] != target:
                continue  # Route doesn't reach destination
            
            if route[0] != start:
                continue  # Route doesn't start from correct position
            
            # VALIDATION: Route should be reasonable length (not truncated)
            if len(route) < len(original_route) * 0.5:
                continue  # Suspiciously short, probably truncated
            
            route_set = set(route)
            
            # Skip if it's the same as original
            if route_set == original_set:
                continue
            
            # TEMPORAL COLLISION CHECK:
            # Project where rerouted train will be at each timestep
            # and check if it collides with priority train
            has_temporal_collision = False
            
            for step_offset, cell in enumerate(route):
                timestep = departure_reroute + step_offset
                
                # Check if priority train is at the same cell at this timestep
                if timestep in priority_occupancy:
                    if priority_occupancy[timestep] == cell:
                        has_temporal_collision = True
                        break
                
                # Also check adjacent timesteps for head-on collisions
                # (trains swapping positions)
                if step_offset > 0:
                    prev_cell = route[step_offset - 1]
                    prev_timestep = timestep - 1
                    
                    # Check if trains are swapping positions (head-on)
                    if (prev_timestep in priority_occupancy and 
                        timestep in priority_occupancy):
                        priority_prev = priority_occupancy.get(prev_timestep)
                        priority_curr = priority_occupancy.get(timestep)
                        
                        if priority_prev == cell and priority_curr == prev_cell:
                            # Trains would swap positions = head-on collision
                            has_temporal_collision = True
                            break
            
            if has_temporal_collision:
                continue  # This route still collides, skip it
            
            # This route avoids temporal collision!
            # Cost = extra travel time
            cost = max(0, len(route) - len(original_route))
            if cost < best_cost:
                best_cost = cost
                best_route = route
        
        if best_route is None:
            return (float('inf'), original_route, [])
        
        return (best_cost, original_route, best_route)
    
    def _find_all_routes(
        self, 
        start: Tuple[int, int], 
        target: Tuple[int, int],
        max_routes: int = 5,
        start_direction: int = None
    ) -> List[List[Tuple[int, int]]]:
        """Find multiple routes from start to target respecting Flatland transitions.
        """
        from collections import deque
        
        grid = self.env.rail.grid
        height, width = grid.shape
        
        if start == target:
            return [[start]]
        
        # Direction offsets: N=0, E=1, S=2, W=3
        dir_offsets = [(-1, 0), (0, 1), (1, 0), (0, -1)]
        
        # BFS with direction tracking: (position, travel_direction, path)
        queue = deque()
        
        # At start, try all possible travel directions
        cell = grid[start]
        for travel_dir in range(4):
            valid_exits = self.rail_trans.get_transitions(cell, travel_dir)
            if any(valid_exits):
                for exit_dir in range(4):
                    if valid_exits[exit_dir]:
                        dr, dc = dir_offsets[exit_dir]
                        next_pos = (start[0] + dr, start[1] + dc)
                        if 0 <= next_pos[0] < height and 0 <= next_pos[1] < width:
                            if grid[next_pos] != 0:
                                queue.append((next_pos, exit_dir, [start, next_pos]))
        
        routes = []
        max_length = height + width + 20
        iterations = 0
        max_iterations = 5000  # Prevent infinite loops
        
        # Track visited states PER route length to allow finding longer alternatives
        # Key: (pos, dir), Value: shortest path length that visited this state
        visited_at_length = {}
        
        while queue and len(routes) < max_routes * 3 and iterations < max_iterations:
            iterations += 1
            pos, travel_dir, path = queue.popleft()
            
            if pos == target:
                # Check if this is a genuinely different route
                path_tuple = tuple(path)
                if path_tuple not in [tuple(r) for r in routes]:
                    routes.append(path)
                continue
            
            if len(path) > max_length:
                continue
            
            # Allow revisiting a state if we're on a different (longer) path
            # This enables finding bypass routes that merge back
            state = (pos, travel_dir)
            if state in visited_at_length:
                # Only skip if a shorter path already explored this state
                # and we're not significantly longer (allow some slack for bypasses)
                if len(path) > visited_at_length[state] + 4:
                    continue
            visited_at_length[state] = min(
                visited_at_length.get(state, float('inf')), 
                len(path)
            )
            
            r, c = pos
            cell = grid[r, c]
            
            if cell == 0:
                continue
            
            valid_exits = self.rail_trans.get_transitions(cell, travel_dir)
            
            for exit_dir in range(4):
                if not valid_exits[exit_dir]:
                    continue
                
                dr, dc = dir_offsets[exit_dir]
                nr, nc = r + dr, c + dc
                next_pos = (nr, nc)
                
                if not (0 <= nr < height and 0 <= nc < width):
                    continue
                
                next_cell = grid[next_pos]
                if next_cell == 0:
                    continue
                
                if next_pos in path:
                    continue
                
                new_path = path + [next_pos]
                
                if next_pos == target:
                    routes.append(new_path)
                else:
                    # Continue traveling in the exit direction
                    queue.append((next_pos, exit_dir, new_path))
        
        # Sort by length and select diverse routes
        routes.sort(key=len)
        
        selected = []
        seen = set()
        for route in routes:
            if len(selected) >= max_routes:
                break
            route_tuple = tuple(route)
            if route_tuple in seen:
                continue
            seen.add(route_tuple)
            
            route_set = set(route)
            is_different = all(
                len(route_set - set(existing)) >= 2 
                for existing in selected
            )
            if is_different or not selected:
                selected.append(route)
        
        return selected
    
    def _hold_cell_penalty(
        self,
        hold_cell,
        hold_until: int,
        holding_train: int,
        timetable,
        projections: Dict,
    ) -> int:
        """
        Return a penalty added to a WAIT option's cost if the hold cell is
        in another train's projected path during the hold period.

        A WAIT that blocks a third train is worse than one that doesn't.
        Penalty = 20 per other train that passes through the hold cell
        during [current_step, hold_until].  This biases the CostCalculator
        toward choosing options that don't create secondary conflicts.
        """
        if hold_cell is None:
            return 0
        penalty = 0
        for tid, proj in projections.items():
            if tid == holding_train:
                continue
            for t, pos in proj.items():
                if t <= hold_until and pos == hold_cell:
                    penalty += 20
                    break
        return penalty

    def generate_all_options(
        self, 
        conflict: Conflict, 
        priorities: Dict[int, float], 
        timetable,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> List[Resolution]:
        """
        Generate ALL possible resolution options for a conflict.
        
        Returns a list of options that can be ranked by CostCalculator.
        
        Args:
            conflict: The conflict to resolve
            priorities: Train priorities (higher = more important)
            timetable: Current timetable
            projections: Position projections for all trains
            
        Returns:
            List of Resolution objects (may be empty if no resolution found)
        """
        options = []
        
        # EARLY VALIDATION: Check both trains exist and have projections
        if conflict.train_a not in projections or conflict.train_b not in projections:
            # Can't resolve - missing projection data
            return options
        
        schedule_a = timetable.get_schedule(conflict.train_a)
        schedule_b = timetable.get_schedule(conflict.train_b)
        if schedule_a is None or schedule_b is None:
            return options
        
        # Determine which train has lower priority (will be delayed)
        priority_a = priorities.get(conflict.train_a, 0)
        priority_b = priorities.get(conflict.train_b, 0)
        
        if priority_a >= priority_b:
            train_to_delay = conflict.train_b
            train_with_priority = conflict.train_a
        else:
            train_to_delay = conflict.train_a
            train_with_priority = conflict.train_b
        
        # Generate WAIT option
        wait_cost, wait_until, wait_at_cell = self.calculate_wait_cost(
            train_to_delay, train_with_priority, conflict, timetable, projections
        )

        if wait_cost < float('inf'):
            # Penalise hold cells that are also in other trains' routes —
            # holding there will create a secondary conflict.
            hold_penalty = self._hold_cell_penalty(
                wait_at_cell, wait_until, train_to_delay, timetable, projections)
            options.append(Resolution(
                resolution_type=ResolutionType.WAIT,
                train_to_delay=train_to_delay,
                delay_added=wait_cost + hold_penalty,
                wait_until=wait_until,
                wait_at_cell=wait_at_cell,
            ))
        
        # Generate REROUTE option
        reroute_cost, original_route, new_route = self.calculate_reroute_option(
            train_to_delay, train_with_priority, timetable
        )
        
        if reroute_cost < float('inf') and new_route:
            options.append(Resolution(
                resolution_type=ResolutionType.REROUTE,
                train_to_delay=train_to_delay,
                delay_added=reroute_cost,
                original_route=original_route,
                new_route=new_route,
            ))
        
        # Also try delaying the OTHER train (even if higher priority)
        # This gives more options for the cost calculator to choose from
        other_train = conflict.train_a if train_to_delay == conflict.train_b else conflict.train_b
        
        # WAIT option for other train
        wait_cost2, wait_until2, wait_at_cell2 = self.calculate_wait_cost(
            other_train, train_to_delay, conflict, timetable, projections
        )
        
        if wait_cost2 < float('inf'):
            options.append(Resolution(
                resolution_type=ResolutionType.WAIT,
                train_to_delay=other_train,
                delay_added=wait_cost2,
                wait_until=wait_until2,
                wait_at_cell=wait_at_cell2,
            ))
        
        # REROUTE option for other train
        reroute_cost2, original_route2, new_route2 = self.calculate_reroute_option(
            other_train, train_to_delay, timetable
        )
        
        if reroute_cost2 < float('inf') and new_route2:
            options.append(Resolution(
                resolution_type=ResolutionType.REROUTE,
                train_to_delay=other_train,
                delay_added=reroute_cost2,
                original_route=original_route2,
                new_route=new_route2,
            ))
        
        return options

    def generate_resolution(
        self, 
        conflict: Conflict, 
        priorities: Dict[int, float], 
        timetable,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> Optional[Resolution]:
        """
        Generate the best resolution for a conflict.
        +
        """
        # EARLY VALIDATION: Check both trains exist and have projections
        if conflict.train_a not in projections or conflict.train_b not in projections:
            return None
        
        schedule_a = timetable.get_schedule(conflict.train_a)
        schedule_b = timetable.get_schedule(conflict.train_b)
        if schedule_a is None or schedule_b is None:
            return None
        
        # Determine which train has lower priority (will be delayed)
        priority_a = priorities.get(conflict.train_a, 0)
        priority_b = priorities.get(conflict.train_b, 0)
        
        if priority_a >= priority_b:
            train_to_delay = conflict.train_b
            train_with_priority = conflict.train_a
        else:
            train_to_delay = conflict.train_a
            train_with_priority = conflict.train_b
        
        # Calculate WAIT option
        wait_cost, wait_until, wait_at_cell = self.calculate_wait_cost(
            train_to_delay, train_with_priority, conflict, timetable, projections
        )
        
        # Calculate REROUTE option
        reroute_cost, original_route, new_route = self.calculate_reroute_option(
            train_to_delay, train_with_priority, timetable
        )
        
        # Choose the better option (lower cost)
        # Prefer WAIT if costs are equal (simpler, no route change)
        if wait_cost <= reroute_cost and wait_cost < float('inf'):
            return Resolution(
                resolution_type=ResolutionType.WAIT,
                train_to_delay=train_to_delay,
                delay_added=wait_cost,
                wait_until=wait_until,
                wait_at_cell=wait_at_cell,
            )
        elif reroute_cost < float('inf'):
            return Resolution(
                resolution_type=ResolutionType.REROUTE,
                train_to_delay=train_to_delay,
                delay_added=reroute_cost,
                original_route=original_route,
                new_route=new_route,
            )
        else:
            return None  # No resolution possible


# ============== CONFLICT RESOLVER ==============

class ConflictResolver:
    """
    Main class that coordinates conflict detection and resolution.
    """
    
    def __init__(self, env, timetable, priorities: Dict[int, float],
                 cost_weights=None, use_cost_calculator: bool = False, verbose: bool = False):
        """
        Initialize the conflict resolver.
        
        Args:
            env: Flatland RailEnv
            timetable: Timetable with train schedules
            priorities: Dict mapping train_id -> priority (higher = more important)
            cost_weights: Optional CostWeights for cost-based decisions (not yet implemented)
            use_cost_calculator: Whether to use cost calculator (not yet implemented)
            verbose: Whether to print verbose output
        """
        self.env = env
        self.timetable = timetable
        self.priorities = priorities
        self.detector = ConflictDetector(env, timetable)
        self.generator = ResolutionGenerator(env)
        self.verbose = verbose
        
        # Cost calculator integration (placeholder)
        self.cost_weights = cost_weights
        self.use_cost_calculator = use_cost_calculator
        self.cost_breakdowns = {}  # Placeholder for cost breakdowns
        
        # Tracking
        self.conflicts_detected: List[Conflict] = []
        self.resolutions_applied: List[Resolution] = []
        self.delayed_trains: Set[int] = set()  # Trains that have been rerouted or held
        
        # Track UNSOLVABLE conflicts
        self.unresolvable_conflicts: List[Tuple[Conflict, str]] = []  # (conflict, reason)
    
    def check_and_resolve(self, current_step, max_iterations: int = 50) -> List[str]:

        from SafetyVerifier import SafetyVerifier
        
        messages = []
        
        # Track attempted resolutions to avoid infinite loops
        # Key: (train_a, train_b, resolution_type, route_hash)
        attempted_resolutions = set()
        
        for iteration in range(max_iterations):

            conflicts, projections = self.detector.detect_conflicts(current_step)
            verifier = SafetyVerifier(self.timetable, max_steps=150)
            _, violations = verifier.verify_safety(verbose=False, ignore_destination_conflicts=True)
            
            # Convert SafetyVerifier violations to Conflict objects
            safety_conflict_pairs = set()
            for v in violations:
                pair = (min(v.train_a, v.train_b), max(v.train_a, v.train_b))
                safety_conflict_pairs.add((pair, v.timestep, v.position))
            
            # Add any violations not already in conflicts list
            existing_pairs = set()
            for c in conflicts:
                pair = (min(c.train_a, c.train_b), max(c.train_a, c.train_b))
                existing_pairs.add(pair)
            
            for (pair, timestep, position) in safety_conflict_pairs:
                if pair not in existing_pairs:
                    # SafetyVerifier found a collision that ConflictDetector missed!
                    conflicts.append(Conflict(
                        train_a=pair[0],
                        train_b=pair[1],
                        cell=position,
                        timestep=timestep,
                    ))
                    existing_pairs.add(pair)
            
            if not conflicts:
                if iteration > 0:
                    messages.append(f"\n✅ All conflicts resolved after {iteration} iteration(s)")
                break
            
            # Find a conflict we haven't fully tried to resolve yet
            resolved_this_iteration = False
            
            # Deduplicate conflicts by pair for this iteration
            seen_pairs = set()
            unique_conflicts = []
            for c in conflicts:
                pair = (min(c.train_a, c.train_b), max(c.train_a, c.train_b))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    unique_conflicts.append(c)
            
            for conflict in unique_conflicts:
                pair = (min(conflict.train_a, conflict.train_b), 
                        max(conflict.train_a, conflict.train_b))
                
                self.conflicts_detected.append(conflict)
                
                # Generate warning message
                messages.append("")
                messages.append("=" * 60)
                messages.append(f"⚠️  CONFLICT DETECTED (iteration {iteration + 1})")
                messages.append("=" * 60)
                messages.append(
                    f"  Train {conflict.train_a} (priority: {self.priorities.get(conflict.train_a, 0):.2f}) "
                    f"and Train {conflict.train_b} (priority: {self.priorities.get(conflict.train_b, 0):.2f})"
                )
                messages.append(f"  Will collide at cell {conflict.cell} at timestep {conflict.timestep}")
                
                # Generate resolution
                resolution = self.generator.generate_resolution(
                    conflict, self.priorities, self.timetable, projections
                )
                
                if resolution:
                    # Create a key to track this specific resolution attempt
                    route_hash = hash(tuple(resolution.new_route)) if resolution.new_route else 0
                    resolution_key = (pair[0], pair[1], resolution.resolution_type.value, route_hash)
                    
                    if resolution_key in attempted_resolutions:
                        # Already tried this exact resolution, skip to avoid loop
                        messages.append(f"  (Skipping - already tried this resolution)")
                        continue
                    
                    attempted_resolutions.add(resolution_key)
                    self.resolutions_applied.append(resolution)
                    self.delayed_trains.add(resolution.train_to_delay)
                    
                    # Apply resolution based on type
                    schedule = self.timetable.get_schedule(resolution.train_to_delay)
                    
                    if resolution.resolution_type == ResolutionType.REROUTE:
                        # Update timetable with new route
                        schedule.route = resolution.new_route
                        schedule.planned_arrival += resolution.delay_added
                        schedule.was_rerouted = True
                        schedule.reroute_delay_added = getattr(schedule, 'reroute_delay_added', 0) + resolution.delay_added
                        
                        messages.append("")
                        messages.append(f"🔀 RESOLUTION: REROUTE Train {resolution.train_to_delay}")
                        messages.append(f"  (Lower priority train takes bypass)")
                        messages.append("")
                        messages.append(f"  Original route ({len(resolution.original_route)} cells):")
                        messages.append(f"    {' → '.join(str(p) for p in resolution.original_route)}")
                        messages.append("")
                        messages.append(f"  New route ({len(resolution.new_route)} cells):")
                        messages.append(f"    {' → '.join(str(p) for p in resolution.new_route)}")
                        messages.append("")
                        messages.append(f"  Additional delay: +{resolution.delay_added} timesteps")
                        
                    elif resolution.resolution_type == ResolutionType.WAIT:
                        # Update timetable with hold instruction
                        schedule.planned_arrival += resolution.delay_added
                        schedule.was_held = True
                        schedule.hold_at_cell = resolution.wait_at_cell
                        schedule.hold_until = resolution.wait_until
                        schedule.wait_delay_added = getattr(schedule, 'wait_delay_added', 0) + resolution.delay_added
                        
                        messages.append("")
                        messages.append(f"⏸️  RESOLUTION: WAIT Train {resolution.train_to_delay}")
                        messages.append(f"  (Lower priority train holds at cell {resolution.wait_at_cell})")
                        messages.append("")
                        messages.append(f"  Wait until timestep: {resolution.wait_until}")
                        messages.append(f"  Additional delay: +{resolution.delay_added} timesteps")
                    
                    messages.append("=" * 60)
                    resolved_this_iteration = True
                    
                    # Re-check if this specific pair still conflicts
                    from SafetyVerifier import SafetyVerifier
                    temp_verifier = SafetyVerifier(self.timetable, max_steps=100)
                    _, temp_violations = temp_verifier.verify_safety(verbose=False, ignore_destination_conflicts=True)
                    
                    # Check if this pair still has collisions
                    still_colliding = False
                    for v in temp_violations:
                        v_pair = (min(v.train_a, v.train_b), max(v.train_a, v.train_b))
                        if v_pair == pair:
                            still_colliding = True
                            break
                    
                    if still_colliding:
                        messages.append("")
                        messages.append(f"⚠️  WARNING: Resolution applied but collision STILL EXISTS!")
                        messages.append(f"   The {resolution.resolution_type.value} did not fully resolve the conflict.")
                        messages.append(f"   This pair will be tracked as PARTIALLY UNRESOLVED.")
                        self.unresolvable_conflicts.append((conflict, 
                            f"Resolution ({resolution.resolution_type.value}) applied but ineffective - trains still collide"))
                    
                    break  # Re-detect conflicts after applying resolution
                else:
                    # Diagnose WHY no resolution was found
                    reason = self._diagnose_unresolvable(conflict, projections)
                    self.unresolvable_conflicts.append((conflict, reason))
                    
                    messages.append("")
                    messages.append(f"❌ UNSOLVABLE CONFLICT - Train {conflict.train_a} vs Train {conflict.train_b}")
                    messages.append(f"  Cell: {conflict.cell}, Timestep: {conflict.timestep}")
                    messages.append(f"  Reason: {reason}")
                    messages.append("")
                    messages.append(f"  ⚠️  WARNING: These trains WILL COLLIDE without manual intervention!")
                    messages.append(f"  Suggestions:")
                    messages.append(f"    - Add bypass route between stations")
                    messages.append(f"    - Stagger departure times further apart")
                    messages.append(f"    - Reduce train density on this corridor")
                    messages.append("=" * 60)
            
            if not resolved_this_iteration:
                # No new resolutions possible
                if conflicts:
                    messages.append(f"\n⚠️  {len(unique_conflicts)} conflict(s) remain unresolved")
                    if self.unresolvable_conflicts:
                        messages.append(f"   Including {len(self.unresolvable_conflicts)} UNSOLVABLE conflict(s)")
                break
        
        return messages
    
    def _diagnose_unresolvable(self, conflict: Conflict, projections: Dict) -> str:
        """
        Diagnose why a conflict cannot be resolved.
        
        Returns a human-readable explanation.
        """
        train_a = conflict.train_a
        train_b = conflict.train_b
        
        schedule_a = self.timetable.get_schedule(train_a)
        schedule_b = self.timetable.get_schedule(train_b)
        
        reasons = []
        
        # Check WAIT feasibility for both trains
        wait_a, _, _ = self.generator.calculate_wait_cost(
            train_a, train_b, conflict, self.timetable, projections
        )
        wait_b, _, _ = self.generator.calculate_wait_cost(
            train_b, train_a, conflict, self.timetable, projections
        )
        
        # Check REROUTE feasibility for both trains
        reroute_a, _, route_a = self.generator.calculate_reroute_option(
            train_a, train_b, self.timetable
        )
        reroute_b, _, route_b = self.generator.calculate_reroute_option(
            train_b, train_a, self.timetable
        )
        
        if wait_a == float('inf') and wait_b == float('inf'):
            reasons.append("Neither train can WAIT (possibly head-on collision)")
        
        if reroute_a == float('inf') and reroute_b == float('inf'):
            reasons.append("No bypass routes available for either train")
        elif reroute_a == float('inf'):
            reasons.append(f"Train {train_a} has no bypass route")
        elif reroute_b == float('inf'):
            reasons.append(f"Train {train_b} has no bypass route")
        
        # Check if trains are already rerouted (bypass already in use)
        if getattr(schedule_a, 'was_rerouted', False):
            reasons.append(f"Train {train_a} already rerouted (bypass in use)")
        if getattr(schedule_b, 'was_rerouted', False):
            reasons.append(f"Train {train_b} already rerouted (bypass in use)")
        
        # Check if trains are already held
        if getattr(schedule_a, 'was_held', False):
            reasons.append(f"Train {train_a} already held")
        if getattr(schedule_b, 'was_held', False):
            reasons.append(f"Train {train_b} already held")
        
        if not reasons:
            reasons.append("Unknown - resolution generation failed")
        
        return "; ".join(reasons)
    
    def get_stats(self) -> Dict:
        """Get statistics about conflicts and resolutions."""
        waits = [r for r in self.resolutions_applied if r.resolution_type == ResolutionType.WAIT]
        reroutes = [r for r in self.resolutions_applied if r.resolution_type == ResolutionType.REROUTE]
        
        return {
            'conflicts_detected': len(self.conflicts_detected),
            'resolutions_applied': len(self.resolutions_applied),
            'waits': len(waits),
            'reroutes': len(reroutes),
            'trains_delayed': list(self.delayed_trains),
            'total_delay_added': sum(r.delay_added for r in self.resolutions_applied),
            'delay_from_waits': sum(r.delay_added for r in waits),
            'delay_from_reroutes': sum(r.delay_added for r in reroutes),
            'options_per_conflict': {},  # Placeholder for compatibility
            'unresolvable_conflicts': len(self.unresolvable_conflicts),
            'unresolvable_pairs': [(c.train_a, c.train_b, reason) for c, reason in self.unresolvable_conflicts],
        }
    
    def print_summary(self):
        """Print summary of conflicts and resolutions."""
        stats = self.get_stats()
        
        print("\n" + "=" * 70)
        print(" CONFLICT RESOLVER SUMMARY")
        print("=" * 70)
        print(f"\n  Conflicts detected: {stats['conflicts_detected']}")
        print(f"  Resolutions applied: {stats['resolutions_applied']}")
        print(f"    - Waits: {stats['waits']}")
        print(f"    - Reroutes: {stats['reroutes']}")
        print(f"  Trains delayed: {stats['trains_delayed']}")
        print(f"  Total delay added: {stats['total_delay_added']} timesteps")
        if stats['waits'] > 0:
            print(f"    - From waits: {stats['delay_from_waits']} timesteps")
        if stats['reroutes'] > 0:
            print(f"    - From reroutes: {stats['delay_from_reroutes']} timesteps")
        
        if self.conflicts_detected:
            print("\n  Conflict details:")
            for c in self.conflicts_detected:
                print(f"    - Train {c.train_a} vs Train {c.train_b} at {c.cell}, timestep {c.timestep}")
        
        if self.resolutions_applied:
            print("\n  Resolution details:")
            for r in self.resolutions_applied:
                if r.resolution_type == ResolutionType.WAIT:
                    print(f"    - Train {r.train_to_delay}: WAIT at {r.wait_at_cell} until step {r.wait_until}, +{r.delay_added} delay")
                else:
                    print(f"    - Train {r.train_to_delay}: REROUTE via bypass, +{r.delay_added} delay")
        
        # CRITICAL: Warn about unresolvable conflicts
        if self.unresolvable_conflicts:
            print("\n" + "!" * 70)
            print(" ⚠️  WARNING: UNSOLVABLE CONFLICTS DETECTED")
            print("!" * 70)
            print(f"\n  {len(self.unresolvable_conflicts)} conflict(s) have NO SOLUTION:")
            print("  These trains WILL COLLIDE without manual intervention!\n")
            
            for conflict, reason in self.unresolvable_conflicts:
                print(f"  ❌ Train {conflict.train_a} vs Train {conflict.train_b}")
                print(f"     Collision at: {conflict.cell}, timestep {conflict.timestep}")
                print(f"     Reason: {reason}")
                print()
            
            print("  RECOMMENDED ACTIONS:")
            print("    1. Add more bypass routes to the track layout")
            print("    2. Increase departure time gaps between conflicting trains")
            print("    3. Reduce the number of trains in this time window")
            print("    4. Change train priorities to allow different resolution order")
            print("!" * 70)
        
        print("=" * 70)
    
    def get_unresolvable_report(self) -> str:
        """
        Get a detailed report of all unresolvable conflicts.
        
        Returns:
            Formatted string report suitable for logging or display
        """
        if not self.unresolvable_conflicts:
            return "✅ All conflicts were successfully resolved."
        
        lines = [
            "",
            "=" * 70,
            " UNRESOLVABLE CONFLICTS REPORT",
            "=" * 70,
            "",
            f" Total unresolvable: {len(self.unresolvable_conflicts)}",
            "",
        ]
        
        for i, (conflict, reason) in enumerate(self.unresolvable_conflicts, 1):
            lines.extend([
                f" {i}. Train {conflict.train_a} vs Train {conflict.train_b}",
                f"    Location: {conflict.cell}",
                f"    Timestep: {conflict.timestep}",
                f"    Reason: {reason}",
                "",
            ])
        
        lines.extend([
            " INFRASTRUCTURE REQUIREMENTS:",
            " To resolve these conflicts, consider:",
            "",
        ])
        
       
        needs_bypass = any("bypass" in reason.lower() for _, reason in self.unresolvable_conflicts)
        needs_timing = any("head-on" in reason.lower() or "wait" in reason.lower() 
                          for _, reason in self.unresolvable_conflicts)
        already_rerouted = any("already rerouted" in reason.lower() 
                               for _, reason in self.unresolvable_conflicts)
        
        if needs_bypass:
            lines.append("   • Additional bypass tracks between key junctions")
        if already_rerouted:
            lines.append("   • Second-level bypass routes (bypass for the bypass)")
        if needs_timing:
            lines.append("   • Larger time gaps between train departures")
            lines.append("   • Dedicated time slots for opposing directions")
        
        lines.extend([
            "",
            "=" * 70,
        ])
        
        return "\n".join(lines)