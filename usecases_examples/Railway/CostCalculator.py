"""
Cost Calculator for train dispatching resolution evaluation.

Provides:
- CostWeights: Configurable weights for cost function components
- SlackInfo: Information about schedule slack/buffer
- CostCalculator: Main class for evaluating resolution costs

Cost components:
1. Direct delay cost (weighted by priority)
2. Cascade delay cost (delays caused to other trains)
3. Slack/robustness penalties and bonuses
4. Route complexity (junction usage, extra length)

Key insight: Slack measures how fragile a schedule is.
Low slack = small disturbance causes cascading conflicts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set, Any
from enum import Enum
import copy


@dataclass
class CostWeights:
    """
    Configurable weights for cost function.
    Set any weight to 0 to disable that component.
    
    Attributes:
        direct_delay: Base cost per timestep of delay
        priority_multiplier: If True, multiply delay by train priority
        cascade_delay: Multiplier for delays caused to OTHER trains
        slack_violation: Penalty when slack < min_safe_slack
        min_safe_slack: Timesteps below which schedule is "fragile"
        robustness_bonus: Reward per timestep of buffer above minimum
        junction_usage: Cost per junction in rerouted path
        route_length: Cost per extra cell vs original route
        critical_delay: Above this = "major incident" applies multiplier
        critical_multiplier: Applied to delays above critical threshold
    """
    # Primary: delay costs
    direct_delay: float = 1.0
    priority_multiplier: bool = True
    cascade_delay: float = 1.5
    
    # Slack/robustness
    slack_violation: float = 3.0
    min_safe_slack: int = 3
    robustness_bonus: float = 0.2
    
    # Network efficiency
    junction_usage: float = 0.1
    route_length: float = 0.05
    
    # Thresholds
    critical_delay: int = 15
    critical_multiplier: float = 2.0
    
    def __str__(self) -> str:
        return (
            f"CostWeights(direct={self.direct_delay}, cascade={self.cascade_delay}, "
            f"slack_viol={self.slack_violation}, robustness={self.robustness_bonus})"
        )


@dataclass
class SlackInfo:
    """
    Information about a train's schedule slack/buffer.
    
    Slack = how much can this train be delayed before causing a conflict
    with another train?
    
    Low slack = fragile schedule, any disturbance causes cascade.
    High slack = robust schedule, can absorb delays.
    """
    train_id: int
    slack_timesteps: int                      # Buffer before next conflict
    dependent_trains: List[int]               # Trains that depend on us
    blocking_sections: List[Tuple[int, int]]  # Track sections we occupy
    earliest_conflict_step: Optional[int]     # When slack runs out
    
    def is_fragile(self, threshold: int = 3) -> bool:
        """Returns True if slack is below threshold."""
        return self.slack_timesteps < threshold
    
    def __str__(self) -> str:
        status = "FRAGILE" if self.is_fragile() else "OK"
        return (
            f"Slack(train={self.train_id}, buffer={self.slack_timesteps} steps, "
            f"dependents={self.dependent_trains}, status={status})"
        )


@dataclass
class CostBreakdown:
    """Detailed breakdown of cost calculation."""
    direct_delay: float = 0.0
    cascade_delay: float = 0.0
    slack_violation: float = 0.0
    robustness_bonus: float = 0.0
    route_complexity: float = 0.0
    total: float = 0.0
    
    # Additional info
    slack_info: Optional[SlackInfo] = None
    cascade_count: int = 0
    explanation: str = ""
    
    def __str__(self) -> str:
        lines = [
            "Cost Breakdown:",
            f"  Direct delay:      {self.direct_delay:>8.2f}",
            f"  Cascade delays:    {self.cascade_delay:>8.2f}",
            f"  Slack violations:  {self.slack_violation:>8.2f}",
            f"  Robustness bonus: -{self.robustness_bonus:>8.2f}",
            f"  Route complexity:  {self.route_complexity:>8.2f}",
            f"  ───────────────────────────",
            f"  TOTAL:             {self.total:>8.2f}",
        ]
        if self.slack_info:
            lines.append(f"\n  Slack: {self.slack_info.slack_timesteps} steps")
        if self.cascade_count > 0:
            lines.append(f"  Cascades: {self.cascade_count}")
        return "\n".join(lines)


class CostCalculator:
    """
    Calculates resolution costs with configurable weights.
    
    Main interface:
    - evaluate_resolution(): Score a single resolution option
    - evaluate_solution(): Score a complete solution (list of resolutions)
    - compare_options(): Rank multiple resolution options
    - calculate_slack(): Get slack info for a train
    
    Usage:
        calculator = CostCalculator(env, timetable)
        
        # Evaluate options
        options = generate_options(conflict)
        ranked = calculator.compare_options(options, projections)
        best_option = ranked[0]
        
        # Get explanation
        print(best_option.cost_breakdown)
    """
    
    def __init__(
        self, 
        env, 
        timetable, 
        weights: Optional[CostWeights] = None,
        verbose: bool = False
    ):
        """
        Initialize the cost calculator.
        
        Args:
            env: Flatland RailEnv
            timetable: Timetable with train schedules
            weights: Optional custom weights (default weights used if None)
            verbose: If True, print debug information
        """
        self.env = env
        self.timetable = timetable
        self.weights = weights or CostWeights()
        self.verbose = verbose
        
        # Cache for expensive calculations
        self._slack_cache: Dict[int, SlackInfo] = {}
        self._junction_cache: Set[Tuple[int, int]] = set()
        self._build_junction_cache()
    
    def _build_junction_cache(self):
        """Identify all junction cells in the grid."""
        from flatland.envs.rail_generators import RailEnvTransitions
        
        grid = self.env.rail.grid
        rail_trans = RailEnvTransitions()
        
        for r in range(grid.shape[0]):
            for c in range(grid.shape[1]):
                cell = grid[r, c]
                if cell == 0:
                    continue
                
                # Count how many direction combinations have transitions
                # A junction has more than 2 valid travel directions
                valid_directions = 0
                for travel_dir in range(4):
                    exits = rail_trans.get_transitions(cell, travel_dir)
                    if any(exits):
                        valid_directions += 1
                
                if valid_directions >= 3:
                    self._junction_cache.add((r, c))
    
    # ==================== MAIN INTERFACE ====================
    
    def evaluate_resolution(
        self,
        resolution,
        projections: Dict[int, Dict[int, Tuple[int, int]]],
        cascade_conflicts: Optional[List] = None
    ) -> Tuple[float, CostBreakdown]:
        """
        Evaluate total cost of a resolution.
        
        Args:
            resolution: Resolution object (REROUTE or WAIT)
            projections: Position projections for all trains
            cascade_conflicts: Optional pre-detected cascade conflicts
            
        Returns:
            Tuple of (total_cost, CostBreakdown)
        """
        w = self.weights
        breakdown = CostBreakdown()
        
        # 1. Direct delay cost
        breakdown.direct_delay = self._calc_direct_delay_cost(resolution)
        
        # 2. Cascade costs
        if cascade_conflicts is None:
            cascade_conflicts = self._detect_cascade_conflicts(resolution, projections)
        breakdown.cascade_delay = self._calc_cascade_cost(
            resolution, projections, cascade_conflicts
        )
        breakdown.cascade_count = len(cascade_conflicts) if cascade_conflicts else 0
        
        # 3. Slack/robustness
        slack_cost, slack_bonus, slack_info = self._calc_slack_cost(
            resolution, projections
        )
        breakdown.slack_violation = slack_cost
        breakdown.robustness_bonus = slack_bonus
        breakdown.slack_info = slack_info
        
        # 4. Route complexity
        breakdown.route_complexity = self._calc_route_cost(resolution)
        
        # Total
        breakdown.total = (
            breakdown.direct_delay +
            breakdown.cascade_delay +
            breakdown.slack_violation -
            breakdown.robustness_bonus +
            breakdown.route_complexity
        )
        
        # Build explanation
        breakdown.explanation = self._build_explanation(resolution, breakdown)
        
        return breakdown.total, breakdown
    
    def evaluate_solution(
        self,
        decisions: List,
        final_timetable=None
    ) -> Tuple[float, Dict]:
        """
        Evaluate a complete solution (list of decisions from tree search).
        
        Args:
            decisions: List of Resolution objects
            final_timetable: Optional final timetable state
            
        Returns:
            Tuple of (total_cost, breakdown_dict)
        """
        total_cost = 0.0
        breakdown = {
            'direct_delay': 0.0,
            'cascade_delay': 0.0,
            'slack_violation': 0.0,
            'robustness_bonus': 0.0,
            'route_complexity': 0.0,
            'decisions': [],
            'total': 0.0,
        }
        
        for decision in decisions:
            cost, dec_breakdown = self.evaluate_resolution(decision, {}, [])
            total_cost += cost
            
            breakdown['direct_delay'] += dec_breakdown.direct_delay
            breakdown['cascade_delay'] += dec_breakdown.cascade_delay
            breakdown['slack_violation'] += dec_breakdown.slack_violation
            breakdown['robustness_bonus'] += dec_breakdown.robustness_bonus
            breakdown['route_complexity'] += dec_breakdown.route_complexity
            breakdown['decisions'].append(dec_breakdown)
        
        # Final timetable evaluation
        if final_timetable:
            final_cost = self._calc_final_timetable_cost(final_timetable)
            breakdown['final_delay'] = final_cost
            total_cost += final_cost
        
        breakdown['total'] = total_cost
        return total_cost, breakdown
    
    def compare_options(
        self,
        resolutions: List,
        projections: Dict[int, Dict[int, Tuple[int, int]]],
        cascade_conflicts_per_option: Optional[List[List]] = None
    ) -> List[Tuple[Any, float, CostBreakdown]]:
        """
        Compare multiple resolutions and rank them by cost.
        
        Args:
            resolutions: List of Resolution objects to compare
            projections: Position projections for all trains
            cascade_conflicts_per_option: Optional list of cascade conflicts
                                          per option (same order as resolutions)
        
        Returns:
            List of (resolution, cost, breakdown) sorted by cost (lowest first)
        """
        results = []
        
        for i, res in enumerate(resolutions):
            cascades = None
            if cascade_conflicts_per_option and i < len(cascade_conflicts_per_option):
                cascades = cascade_conflicts_per_option[i]
            
            cost, breakdown = self.evaluate_resolution(res, projections, cascades)
            results.append((res, cost, breakdown))
        
        # Sort by cost (lowest first)
        results.sort(key=lambda x: x[1])
        
        return results
    
    # ==================== COST COMPONENTS ====================
    
    def _calc_direct_delay_cost(self, resolution) -> float:
        """Cost from direct delay to the rerouted/waiting train."""
        w = self.weights
        delay = resolution.delay_added
        train_id = resolution.train_to_delay
        
        cost = delay * w.direct_delay
        
        # Priority multiplier
        if w.priority_multiplier:
            priority = self.timetable.get_priority(train_id)
            cost *= priority
        
        # Critical delay threshold
        if delay > w.critical_delay:
            excess = delay - w.critical_delay
            cost += excess * w.direct_delay * w.critical_multiplier
        
        if self.verbose:
            print(f"  Direct delay cost: {delay} steps × priority = {cost:.2f}")
        
        return cost
    
    def _calc_cascade_cost(
        self,
        resolution,
        projections: Dict[int, Dict[int, Tuple[int, int]]],
        cascade_conflicts: List
    ) -> float:
        """Cost from delays caused to other trains."""
        w = self.weights
        
        if not cascade_conflicts:
            return 0.0
        
        cost = 0.0
        for conflict in cascade_conflicts:
            # Determine which train is the "other" one affected
            if hasattr(conflict, 'train_a') and hasattr(conflict, 'train_b'):
                other_train = (
                    conflict.train_b 
                    if conflict.train_a == resolution.train_to_delay 
                    else conflict.train_a
                )
            else:
                # Simple conflict tuple format
                other_train = conflict[1] if conflict[0] == resolution.train_to_delay else conflict[0]
            
            # Estimate delay to the other train
            estimated_delay = self._estimate_cascade_delay(conflict, resolution)
            priority = self.timetable.get_priority(other_train)
            
            conflict_cost = estimated_delay * priority * w.cascade_delay
            cost += conflict_cost
            
            if self.verbose:
                print(f"  Cascade to train {other_train}: {estimated_delay} steps × "
                      f"{priority:.2f} priority × {w.cascade_delay} = {conflict_cost:.2f}")
        
        return cost
    
    def _calc_slack_cost(
        self,
        resolution,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> Tuple[float, float, SlackInfo]:
        """
        Calculate slack-related costs and bonuses.
        
        Returns:
            Tuple of (violation_cost, robustness_bonus, slack_info)
        """
        w = self.weights
        train_id = resolution.train_to_delay
        
        # Calculate slack after resolution
        slack_info = self._calculate_slack(train_id, resolution, projections)
        
        violation_cost = 0.0
        robustness_bonus = 0.0
        
        if slack_info.slack_timesteps < w.min_safe_slack:
            # Penalty for being in fragile zone
            deficit = w.min_safe_slack - slack_info.slack_timesteps
            violation_cost = deficit * w.slack_violation
            
            # Extra penalty if zero slack (critical)
            if slack_info.slack_timesteps == 0:
                violation_cost *= 2.0
            
            if self.verbose:
                print(f"  Slack violation: {slack_info.slack_timesteps} < {w.min_safe_slack} "
                      f"→ penalty {violation_cost:.2f}")
        else:
            # Bonus for having buffer
            excess = slack_info.slack_timesteps - w.min_safe_slack
            robustness_bonus = min(excess, 10) * w.robustness_bonus  # Cap bonus at 10 steps
            
            if self.verbose and robustness_bonus > 0:
                print(f"  Robustness bonus: {excess} steps buffer → +{robustness_bonus:.2f}")
        
        return violation_cost, robustness_bonus, slack_info
    
    def _calc_route_cost(self, resolution) -> float:
        """Cost for route complexity (junctions, extra length)."""
        w = self.weights
        
        # Only applies to reroutes
        if resolution.resolution_type.value != "reroute":
            return 0.0
        
        if not resolution.new_route:
            return 0.0
        
        cost = 0.0
        route = resolution.new_route
        
        # Junction count
        junctions = sum(1 for cell in route if cell in self._junction_cache)
        cost += junctions * w.junction_usage
        
        # Extra length vs original
        if resolution.original_route:
            extra_cells = max(0, len(route) - len(resolution.original_route))
            cost += extra_cells * w.route_length
        
        if self.verbose and cost > 0:
            print(f"  Route complexity: {junctions} junctions, "
                  f"{len(route) - len(resolution.original_route or [])} extra cells → {cost:.2f}")
        
        return cost
    
    def _calc_final_timetable_cost(self, final_timetable) -> float:
        """Evaluate final state: total delay vs original plan."""
        w = self.weights
        total_cost = 0.0
        
        for train_id in range(self.env.get_num_agents()):
            schedule = final_timetable.get_schedule(train_id)
            
            if schedule.arrival_delay is not None and schedule.arrival_delay > 0:
                delay = schedule.arrival_delay
                priority = final_timetable.get_priority(train_id)
                
                cost = delay * priority * w.direct_delay
                
                # Critical threshold
                if delay > w.critical_delay:
                    excess = delay - w.critical_delay
                    cost += excess * w.critical_multiplier
                
                total_cost += cost
        
        return total_cost
    
    # ==================== SLACK CALCULATION ====================
    
    def _calculate_slack(
        self,
        train_id: int,
        resolution,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> SlackInfo:
        """
        Calculate how much slack/buffer a train has after resolution.
        
        Slack = minimum time before this train's new schedule conflicts
                with any other train on a shared track section.
        """
        schedule = self.timetable.get_schedule(train_id)
        
        # Get the route (new route if rerouted, original otherwise)
        if (resolution.resolution_type.value == "reroute" and 
            resolution.new_route):
            route = resolution.new_route
        else:
            route = schedule.route
        
        if not route:
            return SlackInfo(
                train_id=train_id,
                slack_timesteps=999,
                dependent_trains=[],
                blocking_sections=[],
                earliest_conflict_step=None
            )
        
        # Find all other trains that could conflict
        dependent_trains = []
        blocking_sections = []
        min_slack = float('inf')
        earliest_conflict = None
        
        for other_id in range(self.env.get_num_agents()):
            if other_id == train_id:
                continue
            
            if other_id not in projections:
                continue
            
            other_projection = projections[other_id]
            
            # Check each cell in our route
            for cell in route:
                # Estimate when we'll be at this cell
                our_time = self._estimate_time_at_cell(train_id, cell, resolution, route)
                
                if our_time is None:
                    continue
                
                # Find when they'll be at this cell
                for their_time, their_pos in other_projection.items():
                    if their_pos == cell:
                        # Calculate buffer
                        time_diff = abs(their_time - our_time)
                        
                        if time_diff < min_slack:
                            min_slack = time_diff
                            earliest_conflict = their_time
                            
                            if other_id not in dependent_trains:
                                dependent_trains.append(other_id)
                            if cell not in blocking_sections:
                                blocking_sections.append(cell)
        
        return SlackInfo(
            train_id=train_id,
            slack_timesteps=int(min_slack) if min_slack != float('inf') else 999,
            dependent_trains=dependent_trains,
            blocking_sections=blocking_sections,
            earliest_conflict_step=earliest_conflict
        )
    
    def calculate_slack_for_train(
        self,
        train_id: int,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> SlackInfo:
        """
        Calculate slack for a train without any resolution applied.
        
        Useful for evaluating initial schedule fragility.
        """
        # Create a dummy "no change" resolution
        from dataclasses import dataclass
        
        @dataclass
        class DummyResolution:
            resolution_type: Any = None
            train_to_delay: int = 0
            delay_added: int = 0
            new_route: List = None
        
        class DummyType:
            value = "none"
        
        dummy = DummyResolution()
        dummy.resolution_type = DummyType()
        dummy.train_to_delay = train_id
        dummy.new_route = None
        
        return self._calculate_slack(train_id, dummy, projections)
    
    def _estimate_time_at_cell(
        self,
        train_id: int,
        cell: Tuple[int, int],
        resolution,
        route: List[Tuple[int, int]]
    ) -> Optional[int]:
        """Estimate when train will reach a specific cell."""
        schedule = self.timetable.get_schedule(train_id)
        
        if cell not in route:
            return None
        
        cell_idx = route.index(cell)
        departure = schedule.planned_departure
        
        # Account for resolution delays
        if resolution.resolution_type.value == "wait" and resolution.wait_until:
            departure = max(departure, resolution.wait_until)
        elif resolution.delay_added:
            departure += resolution.delay_added
        
        # Account for speed
        speed = schedule.speed
        if speed < 1.0:
            steps_per_cell = int(1.0 / speed)
            return departure + (cell_idx * steps_per_cell)
        else:
            return departure + cell_idx
    
    # ==================== HELPER METHODS ====================
    
    def _detect_cascade_conflicts(
        self,
        resolution,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> List:
        """
        Detect new conflicts caused by this resolution.
        
        This simulates the resolution and checks for new conflicts
        that weren't present before.
        """
        # This would integrate with ConflictDetector
        # For now, return empty (caller should provide pre-detected cascades)
        return []
    
    def _estimate_cascade_delay(self, conflict, resolution) -> int:
        """
        Estimate delay to other train from a cascade conflict.
        
        Simple heuristic: minimum wait time to clear the conflict.
        Could be made more sophisticated with deeper simulation.
        """
        # Default estimate: 3 timesteps (one wait cycle)
        # This is conservative; actual delay may be less or more
        return 3
    
    def _build_explanation(self, resolution, breakdown: CostBreakdown) -> str:
        """Build human-readable explanation of cost calculation."""
        lines = []
        
        res_type = resolution.resolution_type.value.upper()
        train = resolution.train_to_delay
        delay = resolution.delay_added
        
        lines.append(f"{res_type} Train {train} (adds {delay} delay)")
        
        if breakdown.direct_delay > 0:
            lines.append(f"  Direct delay: {breakdown.direct_delay:.2f}")
        
        if breakdown.cascade_count > 0:
            lines.append(f"  Causes {breakdown.cascade_count} cascade(s): {breakdown.cascade_delay:.2f}")
        
        if breakdown.slack_info:
            slack = breakdown.slack_info.slack_timesteps
            if slack < self.weights.min_safe_slack:
                lines.append(f"  LOW SLACK WARNING: only {slack} steps buffer")
            else:
                lines.append(f"  Slack: {slack} steps buffer")
        
        if breakdown.robustness_bonus > 0:
            lines.append(f"  Robustness bonus: -{breakdown.robustness_bonus:.2f}")
        
        if breakdown.route_complexity > 0:
            lines.append(f"  Route complexity: +{breakdown.route_complexity:.2f}")
        
        lines.append(f"  TOTAL: {breakdown.total:.2f}")
        
        return "\n".join(lines)
    
    # ==================== UTILITY ====================
    
    def get_regret(
        self,
        chosen_option,
        all_options: List,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ) -> Tuple[float, float, float]:
        """
        Calculate regret: how much worse is chosen vs optimal?
        
        Returns:
            Tuple of (regret, chosen_cost, optimal_cost)
        
        regret = 0 means chosen IS optimal
        regret > 0 means we could have done better
        """
        # Evaluate all options
        ranked = self.compare_options(all_options, projections)
        
        # Find optimal (first in ranked list)
        optimal_cost = ranked[0][1] if ranked else 0.0
        
        # Find chosen option's cost
        chosen_cost, _ = self.evaluate_resolution(chosen_option, projections)
        
        regret = chosen_cost - optimal_cost
        
        return regret, chosen_cost, optimal_cost
    
    def print_comparison(
        self,
        resolutions: List,
        projections: Dict[int, Dict[int, Tuple[int, int]]]
    ):
        """Print formatted comparison of resolution options."""
        ranked = self.compare_options(resolutions, projections)
        
        print("\n" + "=" * 60)
        print(" RESOLUTION OPTIONS COMPARISON")
        print("=" * 60)
        
        for i, (res, cost, breakdown) in enumerate(ranked):
            marker = "★ BEST" if i == 0 else ""
            res_type = res.resolution_type.value.upper()
            
            print(f"\n{i+1}. {res_type} Train {res.train_to_delay} {marker}")
            print(f"   Delay added: {res.delay_added} steps")
            print(f"   Total cost: {cost:.2f}")
            print(breakdown)
        
        print("=" * 60)


# ==================== PRESET WEIGHT CONFIGURATIONS ====================

def get_priority_focused_weights() -> CostWeights:
    """Weights that heavily prioritize high-priority trains."""
    return CostWeights(
        direct_delay=1.0,
        priority_multiplier=True,
        cascade_delay=2.0,      # Cascades are very bad
        slack_violation=4.0,    # Strong penalty for fragility
        min_safe_slack=5,       # Higher slack requirement
        robustness_bonus=0.3,
        junction_usage=0.05,
        route_length=0.02,
        critical_delay=10,      # Lower threshold
        critical_multiplier=3.0,
    )


def get_balanced_weights() -> CostWeights:
    """Balanced weights for general use."""
    return CostWeights()  # Default values


def get_throughput_focused_weights() -> CostWeights:
    """Weights that prioritize total throughput over individual trains."""
    return CostWeights(
        direct_delay=0.5,       # Less penalty for individual delays
        priority_multiplier=False,  # Don't weight by priority
        cascade_delay=2.0,      # Still avoid cascades
        slack_violation=2.0,    # Moderate slack penalty
        min_safe_slack=2,       # Lower slack requirement
        robustness_bonus=0.1,
        junction_usage=0.2,     # Prefer simpler routes
        route_length=0.1,
        critical_delay=20,      # Higher threshold
        critical_multiplier=1.5,
    )


def get_robustness_focused_weights() -> CostWeights:
    """Weights that prioritize schedule robustness/slack."""
    return CostWeights(
        direct_delay=1.0,
        priority_multiplier=True,
        cascade_delay=1.5,
        slack_violation=5.0,    # Heavy penalty for low slack
        min_safe_slack=5,       # High slack requirement
        robustness_bonus=0.5,   # Good bonus for extra buffer
        junction_usage=0.1,
        route_length=0.05,
        critical_delay=15,
        critical_multiplier=2.0,
    )