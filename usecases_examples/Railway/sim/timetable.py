"""
Timetable data structures for the scripted experiment scenarios.

One TrainSchedule per train, built from the scenario's agent_defs
(see build_timetable). Times are simulation steps.

Step convention (measured on Flatland 4.2.6 with this player):
- actual_departure = index of the env.step() during which the train
  appears on route[0]. On time = planned_departure.
- actual_arrival   = index of the env.step() during which the train
  enters its target (Flatland then removes it from the grid).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TrainSchedule:
    """Schedule and runtime record of one train."""
    train_id: int
    planned_departure: int
    planned_arrival: int
    route: List[Tuple[int, int]]          # (row, col) cells, start -> target
    name: str = ""                        # display name from agent_defs ("S 17")

    # Runtime tracking (written by the dispatcher)
    actual_departure: Optional[int] = None
    actual_arrival: Optional[int] = None

    @property
    def departure_delay(self) -> Optional[int]:
        if self.actual_departure is None:
            return None
        return max(0, self.actual_departure - self.planned_departure)

    @property
    def arrival_delay(self) -> Optional[int]:
        if self.actual_arrival is None:
            return None
        return max(0, self.actual_arrival - self.planned_arrival)

    @property
    def is_on_time(self) -> bool:
        return self.actual_arrival is not None and self.actual_arrival <= self.planned_arrival


@dataclass
class Timetable:
    """All train schedules plus optional priorities (default 1.0 each)."""
    schedules: Dict[int, TrainSchedule]
    priorities: Dict[int, float] = field(default_factory=dict)

    def get_schedule(self, train_id: int) -> Optional[TrainSchedule]:
        return self.schedules.get(train_id)

    def get_priority(self, train_id: int) -> float:
        return self.priorities.get(train_id, 1.0)

    def total_delay(self) -> int:
        """Sum of arrival delays of all arrived trains."""
        return sum(s.arrival_delay for s in self.schedules.values()
                   if s.arrival_delay is not None)

    def summary(self) -> str:
        """Plain-text result table (one line per train)."""
        lines = [f"{'Train':<10} {'Dep plan/act':<14} {'Arr plan/act':<14} {'Delay':<6} Status"]
        for tid, s in sorted(self.schedules.items()):
            dep = f"{s.planned_departure}/{s.actual_departure if s.actual_departure is not None else '-'}"
            arr = f"{s.planned_arrival}/{s.actual_arrival if s.actual_arrival is not None else '-'}"
            delay = s.arrival_delay if s.arrival_delay is not None else "-"
            if s.actual_arrival is None:
                status = "NOT ARRIVED"
            else:
                status = "on time" if s.is_on_time else "delayed"
            lines.append(f"{s.name or tid:<10} {dep:<14} {arr:<14} {str(delay):<6} {status}")
        lines.append(f"Total arrival delay: {self.total_delay()} steps")
        return "\n".join(lines)


def build_timetable(env, agent_defs: List[dict], routes: Dict[int, List[Tuple[int, int]]]) -> Timetable:
    """
    Build the timetable from the scenario's agent_defs.

    planned_departure = dep, planned_arrival = arr, name = name
    (bugfix: the old builder ignored arr and name and used dep + route length
    and "Train-i").
    Trains without a route are skipped with a warning.
    """
    schedules: Dict[int, TrainSchedule] = {}
    for i, d in enumerate(agent_defs):
        route = routes.get(i)
        if not route:
            print(f"[timetable] WARNING: no route for train {i} "
                  f"({d['start']} -> {d['target']}), skipped")
            continue
        schedules[i] = TrainSchedule(
            train_id=i,
            planned_departure=int(d["dep"]),
            planned_arrival=int(d.get("arr", int(d["dep"]) + len(route))),
            route=route,
            name=d.get("name", f"Train_{i}"),
        )
    return Timetable(schedules=schedules)
