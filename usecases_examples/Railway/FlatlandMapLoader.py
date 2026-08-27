"""
FlatlandMapLoader - Load pre-generated Flatland environments from .pkl files.

Provides the same interface as create_corridor_env() so all existing code
(ConflictResolver, SafetyVerifier, CostCalculator, etc.) works unchanged.

Usage:
    from FlatlandMapLoader import load_flatland_env, build_timetable_from_env

    # Load map - same return signature as create_corridor_env()
    env, stations, junctions = load_flatland_env("maps/4city_map.pkl")

    # Build a timetable from the loaded agents
    timetable, train_infos, priorities = build_timetable_from_env(env, stations)

Station naming:
    Cities are auto-detected from agent start/target positions.
    Named as CITY_0, CITY_1, ... sorted by (row, col).

"""

import json
from typing import Dict, List, Tuple, Optional
from flatland.envs.persistence import RailEnvPersister
from flatland.envs.rail_generators import RailEnvTransitions


# ============== CITY / JUNCTION DETECTION ==============

def detect_junctions(env) -> List[Tuple[int, int]]:
    """
    Detect all junction cells in the grid.

    A junction is any cell where a train has 3 or more valid travel directions
    (i.e. can branch, not just go straight or turn).
    """
    rail_trans = RailEnvTransitions()
    grid = env.rail.grid
    junctions = []

    for r in range(grid.shape[0]):
        for c in range(grid.shape[1]):
            cell = grid[r, c]
            if cell == 0:
                continue

            # Count directions from which this cell has valid exits
            valid_entry_dirs = 0
            for entry_dir in range(4):
                exits = rail_trans.get_transitions(cell, entry_dir)
                if any(exits):
                    valid_entry_dirs += 1

            if valid_entry_dirs >= 3:
                junctions.append((r, c))

    return junctions


def _cluster_positions(positions: set, cluster_radius: int = 3) -> List[Tuple[int, int]]:
 
    sorted_pos = sorted(positions)
    representatives = []

    for pos in sorted_pos:
        close_to_existing = any(
            abs(pos[0] - rep[0]) + abs(pos[1] - rep[1]) <= cluster_radius
            for rep in representatives
        )
        if not close_to_existing:
            representatives.append(pos)

    return representatives


def detect_stations(
    env,
    name_map: Optional[Dict[Tuple[int, int], str]] = None,
    cluster_radius: int = 3,
) -> Dict[str, Tuple[int, int]]:
   
    positions = set()
    for agent in env.agents:
        if agent.initial_position is not None:
            positions.add(tuple(agent.initial_position))
        if agent.target is not None:
            positions.add(tuple(agent.target))

    # Cluster so one city = one station
    representatives = _cluster_positions(positions, cluster_radius)

    stations = {}
    auto_idx = 0
    for rep in sorted(representatives):
        if name_map and rep in name_map:
            stations[name_map[rep]] = rep
        else:
            stations[f"CITY_{auto_idx}"] = rep
            auto_idx += 1

    return stations


# ============== MAIN LOADER ==============

def load_flatland_env(
    pkl_path: str,
    name_map: Optional[Dict[Tuple[int, int], str]] = None
) -> Tuple:
    """
    Load a Flatland environment from a .pkl file.

    Drop-in replacement for create_corridor_env() — returns the same
    (env, stations, junctions) tuple so all downstream code works unchanged.

    Args:
        pkl_path: Path to .pkl file saved with RailEnvPersister.save()
        name_map: Optional dict mapping (row, col) -> station name.
                  Example: {(5, 0): 'GENEVA', (5, 34): 'ZURICH'}
                  Positions not in the map get auto-names like CITY_0.

    Returns:
        env:       RailEnv instance (already reset)
        stations:  Dict mapping name -> (row, col)
        junctions: List of (row, col) junction positions
    """
    env, _ = RailEnvPersister.load_new(pkl_path)
    env.reset()

    stations = detect_stations(env, name_map)
    junctions = detect_junctions(env)

    print(f"Loaded: {pkl_path}")
    print(f"  Grid: {env.width}x{env.height}")
    print(f"  Agents: {env.get_num_agents()}")
    print(f"  Stations detected: {len(stations)}")
    print(f"  Junctions detected: {len(junctions)}")
    for name, pos in sorted(stations.items()):
        print(f"    {name}: {pos}")

    return env, stations, junctions


# ============== TIMETABLE BUILDER ==============

def build_timetable_from_env(
    env,
    stations: Dict[str, Tuple[int, int]],
    departure_offset: int = 1,
    stagger_departures: bool = True,
) -> Tuple:
    """
    Build a Timetable directly from env.agents.

    Reads each agent's initial_position, initial_direction, and target
    from the loaded env — these are set correctly by flatland's generator
    and work with any map.

    Args:
        env:               Loaded RailEnv
        stations:          Stations dict from load_flatland_env()
        departure_offset:  First train departs at this timestep (default 1)
        stagger_departures: If True, each train departs 1 step later than
                            the previous (avoids spawn collisions)

    Returns:
        timetable:   Timetable object ready for ConflictResolver / SafetyVerifier
        train_infos: Dict mapping train_id -> TrainInfo
        priorities:  Dict mapping train_id -> float priority
    """
    from Timetable import Timetable, TrainSchedule
    from TrainInfo import TrainInfo, TrainType, calculate_priority
    from Corridor_environment import compute_route_bfs

    # Reverse lookup: (row, col) -> station name
    pos_to_name = {v: k for k, v in stations.items()}

    schedules = {}
    train_infos = {}
    priorities = {}

    for i, agent in enumerate(env.agents):
        start = tuple(agent.initial_position)
        target = tuple(agent.target)

        start_dir = int(agent.initial_direction)
        route = compute_route_bfs(
            env, start, target,
            use_transitions=True,
            start_direction=start_dir,
        )
        if not route:
            # Fallback: try all directions (e.g. station with multiple entries)
            route = compute_route_bfs(env, start, target, use_transitions=True)

        if not route:
            print(f"  WARNING: No route for agent {i} ({start} -> {target}), skipping.")
            continue

        # Use agent's own earliest_departure if set, otherwise stagger
        agent_dep = getattr(agent, 'earliest_departure', None)
        if agent_dep and agent_dep > 0:
            departure = agent_dep
        else:
            departure = departure_offset + (i if stagger_departures else 0)

        schedules[i] = TrainSchedule(
            train_id=i,
            planned_departure=departure,
            planned_arrival=departure + len(route),
            route=route,
        )

        start_name = pos_to_name.get(start, str(start))
        target_name = pos_to_name.get(target, str(target))

        train_infos[i] = TrainInfo(
            train_id=i,
            name=f"Train-{i} ({start_name}->{target_name})",
            train_type=TrainType.PASSENGER_LOCAL,
            passenger_count=100,
            connection_frequency=15,
        )
        priorities[i] = calculate_priority(train_infos[i])

    timetable = Timetable(schedules=schedules, priorities=priorities)

    print(f"\nTimetable built: {len(schedules)} trains scheduled")
    for tid, s in sorted(schedules.items()):
        print(f"  {train_infos[tid].name}: dep={s.planned_departure}, "
              f"route_len={len(s.route)}, arr={s.planned_arrival}")

    return timetable, train_infos, priorities


# ============== VISUALIZER ==============

def visualize_loaded_env(env, stations: Dict[str, Tuple[int, int]],
                          junctions: List[Tuple[int, int]], step: int = 0):
    """
    ASCII visualization for any loaded flatland map.
    Works the same as visualize_corridor() in Corridor_environment.py.
    """
    grid = env.rail.grid
    height, width = grid.shape

    station_pos_set = set(stations.values())
    junction_set = set(junctions)

    # Reverse lookup for station names
    pos_to_name = {v: k for k, v in stations.items()}

    display = [['.' for _ in range(width)] for _ in range(height)]

    for r in range(height):
        for c in range(width):
            if grid[r, c] != 0:
                pos = (r, c)
                if pos in station_pos_set:
                    display[r][c] = pos_to_name[pos][0]  # First letter of name
                elif pos in junction_set:
                    display[r][c] = '+'
                else:
                    display[r][c] = '-'

    # Draw agents
    for i, agent in enumerate(env.agents):
        if agent.position is not None:
            r, c = agent.position
            display[r][c] = str(i % 10)

    print(f"\n Step {step} — {env.width}x{env.height} grid:")
    print("    " + "".join(f"{c % 10}" for c in range(width)))
    print("    " + "-" * width)
    for r in range(height):
        print(f"{r:2} |" + "".join(display[r]))

    print()
    for i, agent in enumerate(env.agents):
        pos = agent.position if agent.position else "waiting"
        target = agent.target
        target_name = pos_to_name.get(tuple(target) if target else None, str(target))
        state_name = agent.state.name if hasattr(agent.state, 'name') else str(agent.state)
        print(f"  Train {i}: {pos} -> {target_name} | {state_name}")


# ============== FLATLAND RENDERER ==============

def render_flatland_env(env, show: bool = True):
    """
    Render using Flatland's built-in graphical renderer (PIL/SVG).

    Requires: pip install flatland-rl (PIL renderer is included)

    Args:
        env:  RailEnv instance (after reset)
        show: If True, opens a display window
    """
    try:
        from flatland.utils.rendertools import RenderTool
        renderer = RenderTool(env, gl="PILSVG")
        renderer.render_env(
            show=show,
            show_observations=False,
            show_inactive_agents=True,
        )
        if show:
            input("Press Enter to close renderer...")
        return renderer
    except Exception as e:
        print(f"Renderer unavailable ({e}), use visualize_loaded_env() for ASCII view.")
        return None




# ============== JSON LOADER ==============

def load_flatland_env_from_json(
    json_path: str,
    agent_defs: list,
    max_episode_steps: int = 200,
    template_pkl: str = "maps/4city_map.pkl",
) -> Tuple:
    """
    Load a Flatland env from a drawn_environment_export.json file.
    Drop-in replacement for load_flatland_env() — same (env, stations, junctions) return.

    Args:
        json_path:         Path to .json map file
        agent_defs:        List of dicts: {start, target, dir, dep, arr}
        max_episode_steps: Episode cap (default 200)
        template_pkl:      Existing pkl for structural metadata template

    Returns:
        env, stations, junctions
    """
    import copy
    import pickle
    import tempfile
    import os
    import numpy as np
    from flatland.envs.agent_utils import Agent
    from flatland.envs.rail_trainrun_data_structures import Waypoint
    from flatland.envs.persistence import RailEnvPersister

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    rows = raw["gridDimensions"]["rows"]
    cols = raw["gridDimensions"]["cols"]
    grid_list = raw["grid"]
    print(f"Loaded JSON: {json_path}  ({rows}x{cols})")

    # Build env using proper Flatland 4.x API
    from flatland.envs.rail_grid_transition_map import RailGridTransitionMap
    from flatland.envs.rail_generators import rail_from_grid_transition_map
    from flatland.envs.line_generators import Line, BaseLineGen
    from flatland.envs.rail_trainrun_data_structures import Waypoint as FLWaypoint
    from flatland.envs.rail_env import RailEnv

    grid_np = np.array(grid_list, dtype=np.uint16)
    rail_map = RailGridTransitionMap(
        width=cols, height=rows,
        transitions=RailEnvTransitions(), grid=grid_np
    )

    _agent_defs = agent_defs  # capture for closure

    class _FixedLineGen(BaseLineGen):
        def generate(self, rail, num_agents, hints, num_resets, np_random):
            wps = [
                [[FLWaypoint(d["start"], d["dir"])], [FLWaypoint(d["target"], None)]]
                for d in _agent_defs
            ]
            return Line(agent_waypoints=wps, agent_speeds=[1.0] * len(_agent_defs))

    env = RailEnv(
        width=cols, height=rows,
        rail_generator=rail_from_grid_transition_map(rail_map),
        line_generator=_FixedLineGen(),
        number_of_agents=len(agent_defs),
    )
    env.reset()
    env._max_episode_steps = max_episode_steps

    # Set departure/arrival times on agents
    for i, d in enumerate(agent_defs):
        env.agents[i].earliest_departure = d["dep"]
        env.agents[i].latest_arrival     = d["arr"]

    # Stations from JSON definitions
    stations: Dict[str, Tuple[int, int]] = {}
    for s in raw.get("stations", []):
        stations[f"CITY_{s['id'] - 1}"] = (s["r"], s["c"])
    if not stations:
        stations = detect_stations(env)

    junctions = detect_junctions(env)
    print(f"  Agents: {len(agent_defs)}, Stations: {len(stations)}, Junctions: {len(junctions)}")
    for name, pos in sorted(stations.items()):
        print(f"    {name}: {pos}")

    return env, stations, junctions


# ============== QUICK TEST ==============

if __name__ == "__main__":
    import os

    # Try to load the map generated by Make_map.py
    MAP_PATH = "maps/4city_map.pkl"

    if not os.path.exists(MAP_PATH):
        print(f"Map not found at {MAP_PATH}")
        print("Run Make_map.py first to generate a map.")
    else:
        # Load
        env, stations, junctions = load_flatland_env(MAP_PATH)

        # ASCII visualization
        visualize_loaded_env(env, stations, junctions)

        # Build timetable
        timetable, train_infos, priorities = build_timetable_from_env(env, stations)

        # Run SafetyVerifier on the initial timetable
        from SafetyVerifier import SafetyVerifier
        verifier = SafetyVerifier(timetable, max_steps=150)
        is_safe, violations = verifier.verify_safety(verbose=True)

        print(f"\nInitial timetable safe: {is_safe}")
        if not is_safe:
            print("Conflicts to resolve — run safe_resolver.py next.")