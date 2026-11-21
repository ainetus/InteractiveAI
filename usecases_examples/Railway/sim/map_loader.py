"""
Load a drawn map (maps/mapN.json) into a Flatland RailEnv and find routes.

Kept from the old FlatlandMapLoader.load_flatland_env_from_json and
Corridor_environment.compute_route_bfs (strict-transition branch only).
Everything for .pkl maps and the generated corridor map is gone.
"""

import json
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from flatland.envs.line_generators import BaseLineGen, Line
from flatland.envs.rail_env import RailEnv
from flatland.envs.rail_generators import RailEnvTransitions, rail_from_grid_transition_map
from flatland.envs.rail_grid_transition_map import RailGridTransitionMap
from flatland.envs.rail_trainrun_data_structures import Waypoint

ROOT = Path(__file__).resolve().parent.parent   # package root (maps/ lives here)


def resolve_path(path: str) -> Path:
    """Scenario map paths are relative to the package root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_map_json(map_path: str) -> dict:
    with open(resolve_path(map_path), "r", encoding="utf-8") as f:
        return json.load(f)


def load_env(map_path: str, agent_defs: List[dict], max_episode_steps: int) -> Tuple[RailEnv, Dict[str, Tuple[int, int]]]:
    """
    Build the RailEnv for a scenario.

    agent_defs: [{start, target, dir, dep, arr, name, speed?}, ...]
    max_episode_steps: Flatland episode limit (set by the player from the
        scenario, bugfix K33: was hardcoded to 200).

    Returns env, stations {"Station <id>": (row, col)}.
    """
    raw = load_map_json(map_path)
    rows = raw["gridDimensions"]["rows"]
    cols = raw["gridDimensions"]["cols"]
    grid = np.array(raw["grid"], dtype=np.uint16)
    rail_map = RailGridTransitionMap(width=cols, height=rows,
                                     transitions=RailEnvTransitions(), grid=grid)

    defs = agent_defs

    class _FixedLineGen(BaseLineGen):
        def generate(self, rail, num_agents, hints, num_resets, np_random):
            wps = [[[Waypoint(tuple(d["start"]), d["dir"])], [Waypoint(tuple(d["target"]), None)]]
                   for d in defs]
            return Line(agent_waypoints=wps, agent_speeds=[1.0] * len(defs))

    env = RailEnv(width=cols, height=rows,
                  rail_generator=rail_from_grid_transition_map(rail_map),
                  line_generator=_FixedLineGen(),
                  number_of_agents=len(defs))
    env.reset()
    env._max_episode_steps = max_episode_steps
    for i, d in enumerate(defs):
        env.agents[i].earliest_departure = d["dep"]
        env.agents[i].latest_arrival = d["arr"]

    stations = {f"Station {s['id']}": (s["r"], s["c"]) for s in raw.get("stations", [])}
    return env, stations


def shortest_route(env, start: Tuple[int, int], goal: Tuple[int, int],
                   start_direction: Optional[int]) -> List[Tuple[int, int]]:
    """
    Shortest cell route start -> goal that obeys Flatland transitions.

    Same search as the old compute_route_bfs(use_transitions=True): BFS over
    (cell, facing direction), seeded only with start_direction if given.
    Returns [] if there is no route.
    """
    start, goal = tuple(start), tuple(goal)
    if start == goal:
        return [start]
    grid = env.rail.grid
    height, width = grid.shape
    offsets = [(-1, 0), (0, 1), (1, 0), (0, -1)]       # N, E, S, W
    trans = RailEnvTransitions()
    max_len = height + width + 40

    seeds = [start_direction] if start_direction is not None else range(4)
    queue = deque((start, d, [start]) for d in seeds)
    visited = set()
    while queue:
        pos, facing, path = queue.popleft()
        if len(path) > max_len or (pos, facing) in visited:
            continue
        visited.add((pos, facing))
        cell = grid[pos]
        if cell == 0:
            continue
        exits = trans.get_transitions(cell, facing)
        for d in range(4):
            if not exits[d]:
                continue
            nr, nc = pos[0] + offsets[d][0], pos[1] + offsets[d][1]
            if not (0 <= nr < height and 0 <= nc < width):
                continue
            nxt = grid[nr, nc]
            if nxt == 0 or (nr, nc) in path or not any(trans.get_transitions(nxt, d)):
                continue
            new_path = path + [(nr, nc)]
            if (nr, nc) == goal:
                return new_path
            queue.append(((nr, nc), d, new_path))
    return []


def build_routes(env, agent_defs: List[dict]) -> Dict[int, List[Tuple[int, int]]]:
    """Route per train: honour the start direction, fall back to any direction."""
    routes = {}
    for i, d in enumerate(agent_defs):
        route = shortest_route(env, d["start"], d["target"], d["dir"])
        if not route:
            route = shortest_route(env, d["start"], d["target"], None)
        routes[i] = route
    return routes


def station_markers(scenario: dict) -> List[dict]:
    """Stations from the map JSON plus one start marker per train (old /stations endpoint)."""
    raw = load_map_json(scenario["map"])
    out = [{"id": s["id"], "r": s["r"], "c": s["c"], "name": f"Station {s['id']}"}
           for s in raw.get("stations", [])]
    for i, d in enumerate(scenario.get("agent_defs", [])):
        r, c = d["start"]
        out.append({"id": f"start_{i}", "r": r, "c": c,
                    "name": d.get("name", f"Train_{i}"), "type": "start"})
    return out
