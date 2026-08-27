"""
SafetyVerifier - Independent collision verification for timetables.

"""

from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class SafetyViolation:
    """A detected safety violation."""
    timestep: int
    train_a: int
    train_b: int
    position: Tuple[int, int]
    violation_type: str  # 'same_cell' or 'head_on_swap'
    
    def __str__(self):
        return f"Step {self.timestep}: Train {self.train_a} and Train {self.train_b} at {self.position} ({self.violation_type})"


class SafetyVerifier:
    """
    Independent safety verification for timetables.
    
    Projects all train positions and checks for collisions,
    completely independent of ConflictDetector logic.
    """
    
    def __init__(self, timetable, max_steps: int = 100):
        self.timetable = timetable
        self.max_steps = max_steps
        
    def project_all_positions(self) -> Dict[int, Dict[int, Tuple[Optional[Tuple[int, int]], bool]]]:
        """
        Project all train positions at each timestep.
        
        Returns:
            Dict mapping train_id -> (Dict mapping timestep -> (position, has_arrived))
        """
        projections = {}
        
        for train_id, schedule in self.timetable.schedules.items():
            projections[train_id] = self._project_train(train_id, schedule)
        
        return projections
    
    def _project_train(self, train_id: int, schedule) -> Dict[int, Tuple[Optional[Tuple[int, int]], bool]]:
        """Project one train's positions over time."""
        positions = {}
        route = schedule.route
        
        if not route:
            return positions
        
        # Determine effective departure (accounting for holds)
        effective_departure = schedule.planned_departure
        if getattr(schedule, 'was_held', False) and getattr(schedule, 'hold_until', None):
            effective_departure = max(effective_departure, schedule.hold_until)
        
        # Get speed (default 1.0)
        speed = getattr(schedule, 'speed', 1.0)
        steps_per_cell = int(1.0 / speed) if speed < 1.0 else 1
        
        destination = route[-1]
        
        for step in range(self.max_steps):
            if step < schedule.planned_departure:
                # Not departed yet
                positions[step] = (None, False)
            elif step < effective_departure:
                # Holding at start
                positions[step] = (route[0], False)
            else:
                # Moving along route (accounting for speed)
                steps_moving = step - effective_departure
                route_idx = steps_moving // steps_per_cell
                
                if route_idx >= len(route):
                    # At destination (arrived)
                    positions[step] = (destination, True)
                else:
                    positions[step] = (route[route_idx], route_idx == len(route) - 1)
        
        return positions
    
    def verify_safety(self, verbose: bool = False, 
                      ignore_destination_conflicts: bool = True) -> Tuple[bool, List[SafetyViolation]]:

        projections = self.project_all_positions()
        violations = []
        
        train_ids = list(projections.keys())
        
        for step in range(self.max_steps):
            # Build position -> trains map for this step
            pos_to_trains = defaultdict(list)
            
            for train_id in train_ids:
                proj = projections[train_id].get(step)
                if proj is not None:
                    pos, arrived = proj
                    if pos is not None:
                        pos_to_trains[pos].append((train_id, arrived))
            
            # Check for same-cell collisions
            for pos, train_arrivals in pos_to_trains.items():
                if len(train_arrivals) > 1:
                    # Multiple trains at same cell
                    for i in range(len(train_arrivals)):
                        for j in range(i + 1, len(train_arrivals)):
                            train_a, arrived_a = train_arrivals[i]
                            train_b, arrived_b = train_arrivals[j]
                            
                            # Skip if both have arrived at destination (station capacity ok)
                            if ignore_destination_conflicts and arrived_a and arrived_b:
                                continue
                            
                            violations.append(SafetyViolation(
                                timestep=step,
                                train_a=train_a,
                                train_b=train_b,
                                position=pos,
                                violation_type='same_cell'
                            ))
            
            # Check for head-on swaps (trains passing through each other)
            if step > 0:
                for i, train_a in enumerate(train_ids):
                    for train_b in train_ids[i+1:]:
                        proj_a_now = projections[train_a].get(step)
                        proj_a_prev = projections[train_a].get(step - 1)
                        proj_b_now = projections[train_b].get(step)
                        proj_b_prev = projections[train_b].get(step - 1)
                        
                        if not all([proj_a_now, proj_a_prev, proj_b_now, proj_b_prev]):
                            continue
                        
                        pos_a_now, arrived_a = proj_a_now
                        pos_a_prev, _ = proj_a_prev
                        pos_b_now, arrived_b = proj_b_now
                        pos_b_prev, _ = proj_b_prev
                        
                        # Skip if both have arrived
                        if ignore_destination_conflicts and arrived_a and arrived_b:
                            continue
                        
                        if (pos_a_now and pos_b_now and pos_a_prev and pos_b_prev and
                            pos_a_now == pos_b_prev and pos_b_now == pos_a_prev):
                            violations.append(SafetyViolation(
                                timestep=step,
                                train_a=train_a,
                                train_b=train_b,
                                position=pos_a_now,
                                violation_type='head_on_swap'
                            ))
        
        # Deduplicate
        seen = set()
        unique_violations = []
        for v in violations:
            key = (v.timestep, min(v.train_a, v.train_b), max(v.train_a, v.train_b), v.violation_type)
            if key not in seen:
                seen.add(key)
                unique_violations.append(v)
        
        is_safe = len(unique_violations) == 0
        
        if verbose:
            if is_safe:
                print("✅ SAFETY VERIFIED: No collisions detected")
            else:
                print(f"❌ SAFETY VIOLATION: {len(unique_violations)} collision(s) detected")
                for v in unique_violations[:10]:
                    print(f"   {v}")
                if len(unique_violations) > 10:
                    print(f"   ... and {len(unique_violations) - 10} more")
        
        return is_safe, unique_violations
    
    def get_conflicting_pairs(self, ignore_destination_conflicts: bool = True) -> Set[Tuple[int, int]]:

        _, violations = self.verify_safety(verbose=False, 
                                           ignore_destination_conflicts=ignore_destination_conflicts)
        
        pairs = set()
        for v in violations:
            pair = (min(v.train_a, v.train_b), max(v.train_a, v.train_b))
            pairs.add(pair)
        
        return pairs


def verify_timetable_safety(timetable, 
                            train_names: Dict[int, str] = None,
                            max_steps: int = 100,
                            verbose: bool = True) -> Tuple[bool, List[SafetyViolation]]:

    verifier = SafetyVerifier(timetable, max_steps)
    is_safe, violations = verifier.verify_safety(verbose=False)
    
    if verbose:
        print("\n" + "=" * 60)
        print(" SAFETY VERIFICATION")
        print("=" * 60)
        
        if is_safe:
            print("\n ✅ SAFE: No collisions detected")
        else:
            print(f"\n ❌ UNSAFE: {len(violations)} collision(s)")
            
            # Group by pair
            by_pair = defaultdict(list)
            for v in violations:
                pair = (min(v.train_a, v.train_b), max(v.train_a, v.train_b))
                by_pair[pair].append(v)
            
            print(f"\n Conflicting pairs: {len(by_pair)}")
            for pair, pair_violations in sorted(by_pair.items()):
                name_a = train_names.get(pair[0], f"Train {pair[0]}") if train_names else f"Train {pair[0]}"
                name_b = train_names.get(pair[1], f"Train {pair[1]}") if train_names else f"Train {pair[1]}"
                
                # Get step range
                steps = sorted(set(v.timestep for v in pair_violations))
                step_range = f"steps {steps[0]}-{steps[-1]}" if len(steps) > 1 else f"step {steps[0]}"
                
                print(f"\n   {name_a} vs {name_b} ({len(pair_violations)} violations, {step_range}):")
                
                # Show first few
                for v in pair_violations[:3]:
                    print(f"      Step {v.timestep}: both at {v.position}")
                if len(pair_violations) > 3:
                    print(f"      ... and {len(pair_violations) - 3} more")
        
        print("=" * 60)
    
    return is_safe, violations


def run_safety_check(timetable, train_names: Dict[int, str] = None, max_steps: int = 100) -> bool:
    """
    Simple helper to run a safety check and return True/False.
    
    Prints a one-line result.
    """
    verifier = SafetyVerifier(timetable, max_steps)
    is_safe, violations = verifier.verify_safety(verbose=False, ignore_destination_conflicts=True)
    
    if is_safe:
        print(" ✅ SafetyVerifier: No collisions")
    else:
        pairs = set()
        for v in violations:
            pairs.add((min(v.train_a, v.train_b), max(v.train_a, v.train_b)))
        print(f" ❌ SafetyVerifier: {len(violations)} collision(s) in {len(pairs)} pair(s)")
    
    return is_safe