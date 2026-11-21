"""
Static drawing data of a scenario's line: ZWL (Marey) distances, planned paths and the link map.

Pure functions over the map grid (Flatland transition ints, row-major). Ported from the
standalone prototype's _compute_marey_mapping, /plans and _build_link_map, so the frontend draws
the same diagrams from the context instead of asking the simulator.

Directions: 0 North, 1 East, 2 South, 3 West (direction of travel). The exits of a cell entered in
direction d are (cell >> ((3 - d) * 4)) & 0xF, bit 3 = N, bit 2 = E, bit 1 = S, bit 0 = W.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple

Cell = Tuple[int, int]

_MOVE = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
_DIR_BIT = {0: 8, 1: 4, 2: 2, 3: 1}
_INF = 10 ** 9
EMPTY_LINK_CELL = 1025        # straight track piece drawn where the link map has no cell


def _key(cell: Cell) -> str:
    return f"{cell[0]},{cell[1]}"


def _distances(grid: List[List[int]], start: Cell) -> Dict[Cell, int]:
    """Shortest distance in cells from start to every cell, following the transitions."""
    rows, cols = len(grid), len(grid[0])
    dist_state: Dict[Tuple[int, int, int], int] = {}
    dist_pos: Dict[Cell, int] = {start: 0}
    queue = deque()

    def push(r, c, d, dist):
        cell = grid[r][c]
        for d_in in ([d] if d is not None else range(4)):
            exits = (cell >> ((3 - d_in) * 4)) & 0xF
            for d_out, bit in _DIR_BIT.items():
                if not exits & bit:
                    continue
                dr, dc = _MOVE[d_out]
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols) or grid[nr][nc] == 0:
                    continue
                nd = dist + 1
                if dist_state.get((nr, nc, d_out), _INF) > nd:
                    dist_state[(nr, nc, d_out)] = nd
                    if dist_pos.get((nr, nc), _INF) > nd:
                        dist_pos[(nr, nc)] = nd
                    queue.append((nr, nc, d_out, nd))

    push(start[0], start[1], None, 0)          # any entry direction at the start cell
    while queue:
        r, c, d, dist = queue.popleft()
        if dist_state.get((r, c, d), _INF) < dist:
            continue
        push(r, c, d, dist)
    return dist_pos


def marey_mapping(grid: List[List[int]], start: Cell, end: Cell) -> Dict[str, int]:
    """"r,c" -> distance from start, for the cells on a shortest route start -> end; {} if none."""
    start, end = tuple(start), tuple(end)
    dist_start = _distances(grid, start)
    dist_end = _distances(grid, end)
    total = dist_start.get(end)
    if total is None:
        return {}
    return {_key(cell): d for cell, d in dist_start.items()
            if dist_end.get(cell, _INF) + d == total}


def planned_paths(timetable, mapping: Dict[str, int]) -> Dict[str, List[List[int]]]:
    """
    Per train ("Train_<id>"): the planned path in the ZWL as [step, distance] points.

    The train is planned to leave at planned_departure and to move one cell per step along its
    route; only route cells on the line (in the mapping) are kept.
    """
    out = {}
    for tid, s in sorted(timetable.schedules.items()):
        points = [[s.planned_departure + i, mapping[_key(cell)]]
                  for i, cell in enumerate(s.route) if _key(cell) in mapping]
        out[f"Train_{tid}"] = points
    return out


def link_map(grid: List[List[int]], start: Cell, end: Cell,
             mapping: Optional[Dict[str, int]] = None) -> Optional[dict]:
    """
    The line laid out straight in three rows: the main route in row 1, side tracks above (row 0,
    level -1) and below (row 2, level +1). None if the line has no route.

    - grid: 3 rows of EMPTY_LINK_CELL, as long as the line;
    - mapping: [[r, c], [link_row, x]] from real cells to the three-row view;
    - levels: [[r, c], level] of the side cells.
    """
    start = tuple(start)
    if mapping is None:
        mapping = marey_mapping(grid, start, end)
    if not mapping:
        return None

    main_rows = [int(k.split(",")[0]) for k in mapping]
    main_row_mid = (min(main_rows) + max(main_rows)) / 2

    # every non-empty cell reachable from the start, ignoring the transitions
    rows, cols = len(grid), len(grid[0])
    reached = {start: 0}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for dr, dc in _MOVE.values():
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] != 0 and (nr, nc) not in reached:
                reached[(nr, nc)] = reached[(r, c)] + 1
                queue.append((nr, nc))

    n = max(mapping.values()) + 1
    cells = [[[int(k.split(",")[0]), int(k.split(",")[1])], [1, x]] for k, x in mapping.items()]
    levels = []
    for (r, c), dist in reached.items():
        if _key((r, c)) in mapping:
            continue
        nearest_x = min(mapping.values(), key=lambda x: abs(x - dist))
        level = -1 if r < main_row_mid else 1
        cells.append([[r, c], [0 if level == -1 else 2, nearest_x]])
        levels.append([[r, c], level])
    return {"grid": [[EMPTY_LINK_CELL] * n for _ in range(3)], "mapping": cells, "levels": levels}
