"""
Timetable data structures for train scheduling.

"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class TrainSchedule:
    """Schedule for a single train."""
    train_id: int
    planned_departure: int  # timestep
    planned_arrival: int    # timestep (may be updated if rerouted)
    route: List[Tuple[int, int]]  # list of (row, col) positions
    
    # Train properties
    speed: float = 1.0  # 1.0 = normal, 0.5 = takes 2 steps per cell
    
    # Original plan - NEVER modified after creation
    original_planned_arrival: Optional[int] = None
    original_route_length: Optional[int] = None
    
    # Runtime tracking
    actual_departure: Optional[int] = None
    actual_arrival: Optional[int] = None
    
    # Rerouting / hold tracking
    was_rerouted: bool = False
    was_held: bool = False
    hold_at_cell: Optional[Tuple[int, int]] = None
    hold_until: Optional[int] = None
    reroute_delay_added: int = 0  # total delay added by resolver (WAIT + REROUTE)

    # Injected delay tracking (spontaneous/random delays)
    injected_delay_steps: int = 0   # total steps held due to injection
    _inject_hold_until: int = 0     # internal: step when current injection ends
    
    def __post_init__(self):
        """Store original values on creation."""
        if self.original_planned_arrival is None:
            self.original_planned_arrival = self.planned_arrival
        if self.original_route_length is None:
            self.original_route_length = len(self.route) if self.route else 0
    
    @property
    def departure_delay(self) -> Optional[int]:
        """Delay at departure (vs planned)."""
        if self.actual_departure is None:
            return None
        return max(0, self.actual_departure - self.planned_departure)
    
    @property
    def arrival_delay(self) -> Optional[int]:
        """
        Delay at arrival measured against ORIGINAL plan.
        """
        if self.actual_arrival is None:
            return None
        return max(0, self.actual_arrival - self.original_planned_arrival)
    
    @property
    def is_on_time(self) -> bool:
        """On time = arrived by original planned arrival."""
        if self.actual_arrival is None:
            return False
        return self.actual_arrival <= self.original_planned_arrival


@dataclass
class Timetable:
    """
    Complete timetable for all trains.
    
    Tracks priorities for weighted delay calculation.
    """
    schedules: Dict[int, TrainSchedule]
    priorities: Dict[int, float] = field(default_factory=dict)
    
    def get_schedule(self, train_id: int):
        return self.schedules.get(train_id, None)  # None if not in timetable
    
    def set_priorities(self, priorities: Dict[int, float]):
        """Set train priorities for weighted delay calculation."""
        self.priorities = priorities
    
    def get_priority(self, train_id: int) -> float:
        """Get priority for a train (default 1.0)."""
        return self.priorities.get(train_id, 1.0)
    
    def total_delay(self) -> int:
        """Sum of all arrival delays (unweighted)."""
        total = 0
        for schedule in self.schedules.values():
            if schedule.arrival_delay is not None:
                total += schedule.arrival_delay
        return total
    
    def weighted_delay(self) -> float:
        """
        Priority-weighted total delay.
        
        Formula: sum(delay_i * priority_i) for all trains
        
        This is the key metric for evaluating dispatching decisions.
        A high-priority train's delay counts more than a low-priority one.
        """
        total = 0.0
        for train_id, schedule in self.schedules.items():
            if schedule.arrival_delay is not None:
                priority = self.get_priority(train_id)
                total += schedule.arrival_delay * priority
        return total
    
    def print_summary(self):
        """Print timetable summary and results."""
        print("\n" + "="*70)
        print(" TIMETABLE RESULTS")
        print("="*70)
        
        # Header
        header = (f"{'Train':<6} {'Pri':<5} {'Orig Arr':<9} {'Act Arr':<9} "
                  f"{'Delay':<7} {'Wtd Del':<8} {'Rerouted':<9} {'Status':<10}")
        print(f"\n{header}")
        print("-"*70)
        
        # Per-train results
        total_weighted = 0.0
        for train_id, s in sorted(self.schedules.items()):
            priority = self.get_priority(train_id)
            orig_arr = s.original_planned_arrival
            act_arr = s.actual_arrival if s.actual_arrival is not None else "-"
            delay = s.arrival_delay if s.arrival_delay is not None else 0
            weighted = delay * priority if s.arrival_delay is not None else 0
            total_weighted += weighted
            rerouted = "Yes" if s.was_rerouted else "No"
            
            if s.actual_arrival is None:
                status = "INCOMPLETE"
            elif s.is_on_time:
                status = "✓ ON TIME"
            else:
                status = "✗ DELAYED"
            
            print(f"{train_id:<6} {priority:<5.1f} {orig_arr:<9} {str(act_arr):<9} "
                  f"{delay:<7} {weighted:<8.1f} {rerouted:<9} {status:<10}")
        
        print("-"*70)
        
        # Summary statistics
        print(f"\n  Total Delay (unweighted): {self.total_delay()} timesteps")
        print(f"  Weighted Delay (Σ delay×priority): {self.weighted_delay():.1f}")
        
        on_time = sum(1 for s in self.schedules.values() if s.is_on_time)
        total = len(self.schedules)
        print(f"  On-Time Performance: {on_time}/{total} ({100*on_time/total:.0f}%)")
        
        # Rerouting summary
        rerouted_trains = [tid for tid, s in self.schedules.items() if s.was_rerouted]
        held_trains = [tid for tid, s in self.schedules.items() if s.was_held]
        
        rerouted_or_held = [tid for tid, s in self.schedules.items()
                             if s.was_rerouted or s.was_held]
        injected = [tid for tid, s in self.schedules.items()
                    if s.injected_delay_steps > 0]
        if rerouted_or_held or injected:
            print()
            if rerouted_or_held:
                total_reroute = sum(s.reroute_delay_added for s in self.schedules.values())
                print(f"  Trains Rerouted/Held: {rerouted_or_held}")
                print(f"  Delay from Re-planning: {total_reroute} timesteps")
            if injected:
                total_injected = sum(s.injected_delay_steps for s in self.schedules.values())
                print(f"  Trains with Injected Delays: {injected}")
                print(f"  Total Injected Delay: {total_injected} timesteps")
        
        print("="*70)