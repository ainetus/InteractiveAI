"""
Corridor Environment: A larger, more realistic rail network.

Layout:
- Main east-west corridor (Geneva → Zurich)
- Central hub with multiple junctions
- Branch lines to secondary cities (Bern, Lyon, Basel, Milan)
- Multiple bypass routes

Grid: 35 wide × 20 tall
Stations: 7 cities
"""

import numpy as np
from flatland.envs.rail_env import RailEnv
from flatland.envs.rail_generators import RailGenerator, RailEnvTransitions, RailGridTransitionMap
from flatland.envs.line_generators import LineGenerator
from collections import deque
from typing import List, Tuple, Dict, Optional


# ============== TRACK BUILDING HELPERS ==============

def get_transition(directions: List[str]) -> int:
    """
    Create a transition value for a cell based on allowed movements.
    
    Directions: 'N', 'E', 'S', 'W'
    A train entering from direction X can exit to any other direction in the list.
    """
    rail_trans = RailEnvTransitions()
    
    dir_map = {'N': 0, 'E': 1, 'S': 2, 'W': 3}
    dir_indices = [dir_map[d] for d in directions]
    
    transition = 0
    
    # For each entry direction, set exit to all other directions
    for entry in dir_indices:
        for exit_dir in dir_indices:
            if entry != exit_dir or len(dir_indices) == 1:
                # Flatland transition encoding
                transition |= (1 << (16 - 1 - (entry * 4 + exit_dir)))
    
    return transition


def create_straight_horizontal() -> int:
    """Horizontal straight: ─ (E-W only, no N-S connections)"""
    # Value 1025 is a proper horizontal straight:
    # From E: → E (continue east)
    # From W: → W (continue west)
    # No north or south connections
    return 1025


def create_straight_vertical() -> int:
    """Vertical straight: │ (N-S only, no E-W connections)"""
    # Value 32800 is a proper vertical straight:
    # From N: → N (continue north)
    # From S: → S (continue south)
    # No east or west connections
    return 32800


def create_junction_4way() -> int:
    """4-way junction: ┼ (double-slip allows turning)"""
    # Use double-slip crossing that allows turns at junction
    # 56955 enables: From any direction, can exit to any perpendicular direction
    # 33825 (diamond crossing) only allows straight-through - trains can't turn!
    return 56955  # Double-slip crossover (allows turns)


def create_junction_3way(missing: str) -> int:
    """
    3-way junction (T-junction).
    missing: which direction has no track ('N', 'E', 'S', or 'W')
    """
    # T-junctions encoded for different orientations
    t_junctions = {
        'N': 17411,  # ┬ (no north)
        'S': 38433,  # ┴ (no south)
        'E': 32800,  # ├ (no east)
        'W': 49186,  # ┤ (no west)
    }
    return t_junctions.get(missing, 33825)


def create_corner(dir1: str, dir2: str) -> int:
    """
    Corner connecting two directions.
    
    The corner allows trains to turn between the two specified directions.
    
    Correct values verified by checking Flatland transitions:
    - SE (┌): 16386 - N→E, W→S - connects South vertical to East horizontal
    - NE (└): 72    - S→E, W→N - connects North vertical to East horizontal  
    - SW (┐): 4608  - N→W, E→S - connects South vertical to West horizontal
    - NW (┘): 2064  - E→N, S→W - connects North vertical to West horizontal
    """
    corners = {
        # NE corner (└) - connects N vertical to E horizontal
        ('N', 'E'): 72,
        ('E', 'N'): 72,
        # NW corner (┘) - connects N vertical to W horizontal
        ('N', 'W'): 2064,
        ('W', 'N'): 2064,
        # SE corner (┌) - connects S vertical to E horizontal
        ('S', 'E'): 16386,
        ('E', 'S'): 16386,
        # SW corner (┐) - connects S vertical to W horizontal
        ('S', 'W'): 4608,
        ('W', 'S'): 4608,
    }
    return corners.get((dir1, dir2), 0)


def create_dead_end(direction: str) -> int:
    """
    Dead end (station/terminus) pointing in given direction.
    """
    dead_ends = {
        'N': 32800,  # Entry from south
        'S': 72,     # Entry from north
        'E': 2064,   # Entry from west
        'W': 17411,  # Entry from east
    }
    return dead_ends.get(direction, 0)


# ============== CORRIDOR ENVIRONMENT ==============

def create_corridor_env(n_agents: int = 2, agent_configs: List = None):
    """
    Create the corridor environment.
    
    Layout (35×20):
    
              0         10        20        30
         0    ..........S.................S....     BERN(10,0)  BASEL(27,0)
              ..........|.................|....
              ..........+---+.........+---+....     Northern connections
              ..........|...|.........|...|....
         5    S---------+---+---------+---+----S    GENEVA(0,5) ─── ZURICH(34,5)
              ..........|...|.........|...|....     Main corridor + Hub
              ..........+---+---------+---+....     
              ..........|...............|......     
        10    ..........S...............S......     LYON(10,10)  MILAN(24,10)
              ....................................
    
    Stations:
        GENEVA:  (5, 0)   - West terminus
        ZURICH:  (5, 34)  - East terminus  
        BERN:    (0, 12)  - North branch
        BASEL:   (0, 27)  - Northeast
        LYON:    (10, 7)  - Southwest branch
        MILAN:   (10, 27) - Southeast branch
    
    Returns:
        env: RailEnv instance
        stations: Dict of station names to positions
        junctions: List of junction positions
    """
    
    height = 12
    width = 35
    
    # Initialize empty grid
    grid = np.zeros((height, width), dtype=np.uint16)
    
    # Define stations (row, col)
    stations = {
        'GENEVA': (5, 0),
        'ZURICH': (5, 34),
        'BERN': (0, 12),
        'BASEL': (0, 27),
        'LYON': (10, 7),
        'MILAN': (10, 27),
    }
    
    # Track pieces
    H = create_straight_horizontal()  # ─
    V = create_straight_vertical()    # │
    
    # Corners
    NE = create_corner('N', 'E')  # └
    NW = create_corner('N', 'W')  # ┘
    SE = create_corner('S', 'E')  # ┌
    SW = create_corner('S', 'W')  # ┐
    
    # T-junctions
    T_N = create_junction_3way('N')  # ┬
    T_S = create_junction_3way('S')  # ┴
    T_E = create_junction_3way('E')  # ├
    T_W = create_junction_3way('W')  # ┤
    
    # 4-way junction
    X = create_junction_4way()  # ┼
    
    # ===== BUILD THE TRACK =====
    
    # Main corridor: Row 5, from col 0 to 34
    for c in range(35):
        grid[5, c] = H
    
    # ===== WESTERN HUB (around col 7-12) =====
    
    # Junction at (5, 7) - connects to Lyon
    grid[5, 7] = T_N  # Main line with branch south
    
    # Track down to Lyon: col 7, rows 6-9
    for r in range(6, 10):
        grid[r, 7] = V
    grid[10, 7] = V  # Lyon station
    
    # Junction at (5, 12) - connects to Bern
    grid[5, 12] = T_S  # Main line with branch north
    
    # Track up to Bern: col 12, rows 1-4
    for r in range(1, 5):
        grid[r, 12] = V
    grid[0, 12] = V  # Bern station
    
    # ===== WESTERN BYPASS (rows 3-7, cols 7-12) =====
    
    # Northern bypass track
    # Use 4-way junctions at corners to allow through-traffic
    grid[3, 7] = X   # Was SE corner, now junction for Lyon route
    for c in range(8, 12):
        grid[3, c] = H  # Horizontal track
    grid[3, 12] = X  # Was SW corner, now junction for Bern route
    
    # Connect bypass to main junctions
    # Upgrade (5,7) to 4-way
    grid[5, 7] = X
    # Add vertical connector at (4,7)
    grid[4, 7] = V
    # Connect (3,7) properly - it's SE corner coming from junction
    
    # Upgrade (5,12) to 4-way
    grid[5, 12] = X
    # Add vertical connector at (4,12)
    grid[4, 12] = V
    
    # Southern bypass track (rows 7-8)
    # Use 4-way junctions at corners to allow through-traffic (Lyon route)
    grid[7, 7] = X   # Was NE corner, now junction for Lyon route
    for c in range(8, 12):
        grid[7, c] = H
    grid[7, 12] = X  # Was NW corner, now junction
    
    # Connect southern bypass
    grid[6, 7] = V
    grid[6, 12] = V
    
    # ===== EASTERN HUB (around col 22-27) =====
    
    # Junction at (5, 22) - start of eastern hub
    grid[5, 22] = T_N  # Main line with branch south
    
    # Junction at (5, 27) - connects to Basel and Milan
    grid[5, 27] = X  # 4-way junction
    
    # Track up to Basel: col 27, rows 1-4
    for r in range(1, 5):
        grid[r, 27] = V
    grid[0, 27] = V  # Basel station
    
    # Track down to Milan: col 27, rows 6-9
    for r in range(6, 10):
        grid[r, 27] = V
    grid[10, 27] = V  # Milan station
    
    # ===== EASTERN BYPASS =====
    
    # Northern bypass
    grid[3, 22] = SE  # ┌
    for c in range(23, 27):
        grid[3, c] = H
    grid[3, 27] = SW  # ┐ connects to Basel line
    
    # Upgrade junction and add connectors
    grid[5, 22] = X
    grid[4, 22] = V
    grid[4, 27] = V  # Already have vertical from Basel
    
    # Actually (3,27) needs to connect to the vertical going to Basel
    # Make (3,27) a T-junction instead
    grid[3, 27] = T_E  # ├ - connects W, N, S
    
    # Southern bypass  
    grid[7, 22] = NE  # └
    for c in range(23, 27):
        grid[7, c] = H
    grid[7, 27] = T_E  # ├ connects to Milan line
    
    grid[6, 22] = V
    grid[6, 27] = V
    
    
    # ===== MIDDLE CONNECTOR (optional bypass between hubs) =====
    
    # Connect the two hub areas with an alternative route
    # Upper middle: row 3, cols 12-22
    for c in range(13, 22):
        grid[3, c] = H
    
    # Lower middle: row 7, cols 12-22
    for c in range(13, 22):
        grid[7, c] = H
    
    # Update corners to 4-way junctions where bypasses meet vertical tracks
    # These need full connectivity for routes like Lyon→Basel
    grid[3, 12] = X  # 4-way junction for Bern vertical + bypass
    grid[3, 22] = X  # 4-way junction for eastern bypass
    grid[7, 12] = X  # 4-way junction for southern vertical + bypass
    grid[7, 22] = X  # 4-way junction for eastern bypass
    
    # Stations should be proper termini or through-stations
    
    # Geneva (5, 0) - western terminus
    grid[5, 0] = H  # Simple endpoint
    
    # Zurich (5, 34) - eastern terminus
    grid[5, 34] = H  # Simple endpoint
    
    # Bern (0, 12) - northern terminus
    grid[0, 12] = V  # Simple endpoint
    
    # Basel (0, 27) - northern terminus
    grid[0, 27] = V  # Simple endpoint
    
    # Lyon (10, 7) - southern terminus
    grid[10, 7] = V  # Simple endpoint
    
    # Milan (10, 27) - southern terminus
    grid[10, 27] = V  # Simple endpoint
    
    # ===== JUNCTION LIST =====
    junctions = [
        (5, 7),   # West hub - main junction
        (5, 12),  # West hub - Bern junction
        (5, 22),  # East hub - entry
        (5, 27),  # East hub - Basel/Milan junction
        (3, 7),   # North bypass west
        (3, 12),  # North bypass west-mid
        (3, 22),  # North bypass east-mid
        (3, 27),  # North bypass east
        (7, 7),   # South bypass west
        (7, 12),  # South bypass west-mid
        (7, 22),  # South bypass east-mid
        (7, 27),  # South bypass east
    ]
    
    # ===== CREATE ENVIRONMENT =====
    
    # Create transition map
    rail_trans = RailEnvTransitions()
    grid_transition_map = RailGridTransitionMap(width=width, height=height, transitions=rail_trans)
    grid_transition_map.grid = grid
    
    def custom_rail_generator(width, height, num_agents, num_resets=0, np_random=None):
        return grid_transition_map, None
    
    # Default agent configurations
    default_agent_configs = [
        # (start_pos, start_dir, target_pos, target_dir)
        (stations['GENEVA'], 1, stations['ZURICH'], 3),   # Geneva → Zurich (E)
        (stations['ZURICH'], 3, stations['GENEVA'], 1),   # Zurich → Geneva (W)
        (stations['BERN'], 2, stations['MILAN'], 0),      # Bern → Milan (S)
        (stations['MILAN'], 0, stations['BERN'], 2),      # Milan → Bern (N)
        (stations['LYON'], 0, stations['BASEL'], 2),      # Lyon → Basel (N then E)
        (stations['BASEL'], 2, stations['LYON'], 0),      # Basel → Lyon (S then W)
        (stations['GENEVA'], 1, stations['BERN'], 2),     # Geneva → Bern
        (stations['MILAN'], 0, stations['ZURICH'], 3),    # Milan → Zurich
    ]
    
    configs_to_use = agent_configs if agent_configs else default_agent_configs[:n_agents]
    
    def custom_line_generator(rail, num_agents, hints=None, num_resets=0, np_random=None):
        from flatland.envs.timetable_utils import Line
        
        agent_positions = []
        agent_directions = []
        agent_targets = []
        agent_speeds = []
        
        for i in range(min(num_agents, len(configs_to_use))):
            start_pos, start_dir, target_pos, target_dir = configs_to_use[i]
            agent_positions.append([start_pos, target_pos])
            agent_directions.append([start_dir, target_dir])
            agent_targets.append(target_pos)
            agent_speeds.append(1.0)
        
        # Handle different Flatland versions
        fields = Line._fields if hasattr(Line, '_fields') else []
        
        if len(fields) == 2:
            try:
                from flatland.envs.rail_trainrun_data_structures import Waypoint
            except ImportError:
                from flatland.envs.timetable_utils import Waypoint
            
            waypoints = []
            for i in range(len(agent_targets)):
                wp = [
                    [Waypoint(position=agent_positions[i][0], direction=agent_directions[i][0])],
                    [Waypoint(position=agent_targets[i], direction=agent_directions[i][1])],
                ]
                waypoints.append(wp)
            return Line(waypoints, agent_speeds)
        else:
            return Line(agent_positions, agent_directions, agent_targets, agent_speeds)
    
    def custom_timetable_generator(agents, distance_map, agent_hint, max_episode_steps=None):
        from flatland.envs.timetable_utils import Timetable
        
        earliest_departures = []
        latest_arrivals = []
        
        for agent in agents:
            earliest_departures.append([0, None])
            latest_arrivals.append([None, 100])
        
        return Timetable(earliest_departures, latest_arrivals, max_episode_steps or 100)
    
    env = RailEnv(
        width=width,
        height=height,
        rail_generator=custom_rail_generator,
        line_generator=custom_line_generator,
        timetable_generator=custom_timetable_generator,
        number_of_agents=n_agents,
    )
    
    env._max_episode_steps = 100
    
    return env, stations, junctions


# ============== VISUALIZATION ==============

def visualize_corridor(env, stations: Dict, junctions: List, step: int = 0):
    """
    Print a visual representation of the corridor environment.
    """
    grid = env.rail.grid
    height, width = grid.shape
    
    # Reverse lookup: position → station name
    station_positions = {v: k[0] for k, v in stations.items()}  # First letter of name
    junction_set = set(junctions)
    
    # Build display grid
    display = [['.' for _ in range(width)] for _ in range(height)]
    
    for r in range(height):
        for c in range(width):
            if grid[r, c] != 0:
                pos = (r, c)
                if pos in stations.values():
                    # Find station name
                    for name, spos in stations.items():
                        if spos == pos:
                            display[r][c] = name[0]  # First letter
                            break
                elif pos in junction_set:
                    display[r][c] = '+'
                elif r == 5:  # Main corridor
                    display[r][c] = '='
                elif r == 3 or r == 7:  # Bypass routes
                    display[r][c] = '-'
                else:
                    display[r][c] = '|'
    
    # Draw agents
    for i, agent in enumerate(env.agents):
        if agent.position is not None:
            r, c = agent.position
            display[r][c] = str(i)
    
    # Print
    print(f"\n Step {step}:")
    print("    " + "".join(f"{c%10}" for c in range(width)))
    print("    " + "-" * width)
    for r in range(height):
        print(f"{r:2} |" + "".join(display[r]))
    
    # Print agent status
    print()
    for i, agent in enumerate(env.agents):
        pos = agent.position if agent.position else "waiting"
        state_name = agent.state.name if hasattr(agent.state, 'name') else str(agent.state)
        target = agent.target
        # Find target name
        target_name = "?"
        for name, spos in stations.items():
            if spos == target:
                target_name = name
                break
        print(f"  Train {i}: {pos} → {target_name} ({target}) | state: {state_name}")


def print_track_layout(stations: Dict, junctions: List):
    """Print a schematic of the track layout."""
    print("""
    CORRIDOR ENVIRONMENT LAYOUT
    ===========================
    
              0         10        20        30    
         0    ..........B.................B....     BERN(0,12)  BASEL(0,27)
              ..........|.................|....
              ..........+---+.........+---+....     Northern bypass
              ..........|...|.........|...|....
         5    G=========+===+=========+===+====Z    GENEVA(5,0) ─── ZURICH(5,34)
              ..........|...|.........|...|....     Main corridor + Hubs
              ..........+---+---------+---+....     Southern bypass
              ..........|...............|......     
        10    ..........L...............M......     LYON(10,7)  MILAN(10,27)
    
    Legend:
        G/Z = Geneva/Zurich (main corridor termini)
        B = Bern/Basel (northern branches)
        L/M = Lyon/Milan (southern branches)
        + = Junction
        = = Main corridor
        - = Bypass routes
        | = Branch lines
    
    Key Routes:
        Geneva ↔ Zurich: Main corridor (direct) or via bypasses
        Bern ↔ Milan: Through western and eastern hubs
        Lyon ↔ Basel: Cross-network diagonal
    """)
    
    print("Stations:", stations)
    print(f"Junctions: {len(junctions)} total")


# ============== MULTI-ROUTE BFS ==============

def compute_all_routes_bfs(env, start: Tuple[int, int], goal: Tuple[int, int], 
                           max_routes: int = 5, 
                           key_junctions: List[Tuple[int, int]] = None,
                           use_transitions: bool = False,
                           start_direction: Optional[int] = None) -> List[List[Tuple[int, int]]]:
    """
    Find multiple routes from start to goal using BFS.

    Args:
        env: Rail environment
        start: Starting position (row, col)
        goal: Goal position (row, col)
        max_routes: Maximum number of routes to return
        key_junctions: Optional list of junction positions for route diversity
        use_transitions: If True, use strict Flatland transition checking (required
                         for loaded flatland maps). If False, use simple connectivity.
        start_direction: If given, seed BFS only with this direction. This MUST
                         match agent.initial_direction for loaded maps so that
                         route[0]->route[1] is compatible with how the agent spawns.
                         Without this, the BFS may return routes starting in the
                         opposite direction to initial_direction, causing an immediate
                         OFF-ROUTE on the first step.
    """
    if start == goal:
        return [[start]]
    
    grid = env.rail.grid
    height, width = grid.shape
    
    # Direction offsets: N=0, E=1, S=2, W=3
    dir_offsets = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    
    if use_transitions:
        # Strict mode: use Flatland's transition system
        from flatland.envs.rail_generators import RailEnvTransitions
        rail_trans = RailEnvTransitions()
        opposite_dir = [2, 3, 0, 1]
        
        queue = deque()
        # If start_direction given, only seed from that direction.
        # This ensures route[0]->route[1] matches agent.initial_direction.
        seed_dirs = [start_direction] if start_direction is not None else range(4)
        for initial_dir in seed_dirs:
            queue.append((start, initial_dir, [start]))
        
        found_routes = []
        visited = set()
        max_path_length = height + width + 40
        
        while queue and len(found_routes) < max_routes * 10:
            pos, facing_dir, path = queue.popleft()
            
            if len(path) > max_path_length:
                continue
            
            state = (pos, facing_dir)
            if state in visited:
                continue
            visited.add(state)
            
            r, c = pos
            cell = grid[r, c]
            
            if cell == 0:
                continue
            
            valid_exits = rail_trans.get_transitions(cell, facing_dir)
            
            for exit_dir in range(4):
                if not valid_exits[exit_dir]:
                    continue
                
                dr, dc = dir_offsets[exit_dir]
                nr, nc = r + dr, c + dc
                
                if not (0 <= nr < height and 0 <= nc < width):
                    continue
                
                next_cell = grid[nr, nc]
                if next_cell == 0 or (nr, nc) in path:
                    continue
                
                # Train continues traveling in the same direction (exit_dir)
                travel_dir = exit_dir
                next_valid = rail_trans.get_transitions(next_cell, travel_dir)
                if not any(next_valid):
                    continue
                
                new_path = path + [(nr, nc)]
                
                if (nr, nc) == goal:
                    found_routes.append(new_path)
                else:
                    queue.append(((nr, nc), travel_dir, new_path))
    else:
        # Simple mode: just check if cells are connected (non-zero neighbors)
        queue = deque([(start, [start])])
        found_routes = []
        visited_at_length = {}
        max_path_length = height + width + 40
        
        while queue and len(found_routes) < max_routes * 10:
            pos, path = queue.popleft()
            
            if len(path) > max_path_length:
                continue
            
            # Allow revisiting with slightly longer paths for diversity
            if pos in visited_at_length and len(path) > visited_at_length[pos] + 5:
                continue
            visited_at_length[pos] = min(visited_at_length.get(pos, 999), len(path))
            
            r, c = pos
            cell = grid[r, c]
            
            if cell == 0:
                continue
            
            for dr, dc in dir_offsets:
                nr, nc = r + dr, c + dc
                
                if 0 <= nr < height and 0 <= nc < width:
                    next_cell = grid[nr, nc]
                    
                    if next_cell != 0 and (nr, nc) not in path:
                        new_path = path + [(nr, nc)]
                        
                        if (nr, nc) == goal:
                            found_routes.append(new_path)
                        else:
                            queue.append(((nr, nc), new_path))
    
    # Sort by length
    found_routes.sort(key=len)
    
    # Remove duplicates and select diverse routes
    unique_routes = []
    seen_paths = set()
    
    for route in found_routes:
        route_tuple = tuple(route)
        if route_tuple in seen_paths:
            continue
        seen_paths.add(route_tuple)
        
        if len(unique_routes) >= max_routes:
            break
        
        route_rows = set(p[0] for p in route)
        
        is_different = True
        for existing in unique_routes:
            existing_rows = set(p[0] for p in existing)
            
            if route_rows == existing_rows:
                route_middle = set(route[len(route)//3 : 2*len(route)//3])
                existing_middle = set(existing[len(existing)//3 : 2*len(existing)//3])
                
                if route_middle and existing_middle:
                    overlap = len(route_middle & existing_middle) / max(len(route_middle), len(existing_middle))
                    if overlap > 0.7:
                        is_different = False
                        break
        
        if is_different:
            unique_routes.append(route)
    
    return unique_routes


def compute_route_bfs(env, start: Tuple[int, int], goal: Tuple[int, int], 
                      use_transitions: bool = False,
                      start_direction: Optional[int] = None) -> List[Tuple[int, int]]:
    """
    Find the shortest route from start to goal.

    Args:
        env: Rail environment
        start: Starting position
        goal: Goal position
        use_transitions: If True, use strict Flatland transition rules (required for
                         loaded flatland maps).
        start_direction: If given, constrain BFS to start in this direction only.
                         Pass agent.initial_direction for loaded maps.
    """
    routes = compute_all_routes_bfs(
        env, start, goal, max_routes=1,
        use_transitions=use_transitions,
        start_direction=start_direction,
    )
    return routes[0] if routes else []


# ============== TESTING ==============

def test_environment():
    """Test the corridor environment."""
    print("=" * 60)
    print("TESTING CORRIDOR ENVIRONMENT")
    print("=" * 60)
    
    # Create environment with 2 agents
    env, stations, junctions = create_corridor_env(n_agents=2)
    env.reset()
    
    # Print layout
    print_track_layout(stations, junctions)
    
    # Visualize
    visualize_corridor(env, stations, junctions, step=0)
    
    # Test route finding
    print("\n" + "=" * 60)
    print("ROUTE FINDING TEST")
    print("=" * 60)
    
    test_pairs = [
        ('GENEVA', 'ZURICH'),
        ('BERN', 'MILAN'),
        ('LYON', 'BASEL'),
        ('GENEVA', 'BERN'),
    ]
    
    for start_name, goal_name in test_pairs:
        start = stations[start_name]
        goal = stations[goal_name]
        
        print(f"\n{start_name} → {goal_name}:")
        routes = compute_all_routes_bfs(env, start, goal, max_routes=3, key_junctions=junctions)
        
        if routes:
            for i, route in enumerate(routes):
                # Analyze which rows (bypasses) the route uses
                rows_used = sorted(set(p[0] for p in route))
                row_desc = []
                if 3 in rows_used:
                    row_desc.append("north bypass")
                if 5 in rows_used:
                    row_desc.append("main corridor")
                if 7 in rows_used:
                    row_desc.append("south bypass")
                
                print(f"  Route {i+1}: {len(route)} cells via {', '.join(row_desc)}")
        else:
            print("  No route found!")
    
    return env, stations, junctions


def visualize_route(env, stations: Dict, route: List[Tuple[int, int]], route_name: str = ""):
    """Visualize a specific route on the grid."""
    grid = env.rail.grid
    height, width = grid.shape
    
    route_set = set(route)
    
    # Build display grid
    display = [['.' for _ in range(width)] for _ in range(height)]
    
    for r in range(height):
        for c in range(width):
            if grid[r, c] != 0:
                pos = (r, c)
                if pos in route_set:
                    display[r][c] = '*'
                elif pos in stations.values():
                    for name, spos in stations.items():
                        if spos == pos:
                            display[r][c] = name[0]
                            break
                elif r == 5:
                    display[r][c] = '='
                elif r == 3 or r == 7:
                    display[r][c] = '-'
                else:
                    display[r][c] = '|'
    
    # Mark start and end
    if route:
        sr, sc = route[0]
        er, ec = route[-1]
        display[sr][sc] = 'S'
        display[er][ec] = 'E'
    
    print(f"\n Route: {route_name}")
    print("    " + "".join(f"{c%10}" for c in range(width)))
    for r in range(height):
        print(f"{r:2} |" + "".join(display[r]))


# ============== MAP LOADER (delegates to FlatlandMapLoader) ==============

def load_corridor_env(pkl_path: str, name_map=None):
    """
    Load a pre-generated Flatland map from a .pkl file.
    Delegates to FlatlandMapLoader.load_flatland_env — kept here for
    backward-compatible imports.
    """
    from FlatlandMapLoader import load_flatland_env
    return load_flatland_env(pkl_path, name_map=name_map)


def build_timetable_from_loaded_env(env, stations, departure_offset=1,
                                     stagger_departures=True):
    """
    Build a timetable from a loaded env's agents.
    Delegates to FlatlandMapLoader.build_timetable_from_env.
    """
    from FlatlandMapLoader import build_timetable_from_env
    return build_timetable_from_env(env, stations, departure_offset,
                                    stagger_departures)
