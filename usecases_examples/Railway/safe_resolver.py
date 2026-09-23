"""
Safe Conflict Resolution with Verification.
"""

from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy

from flatland.envs.rail_env import RailEnv

from Timetable import Timetable, TrainSchedule
from TrainInfo import TrainInfo
from ConflictResolver import ConflictDetector, ResolutionGenerator, ResolutionType
from CostCalculator import CostCalculator, get_priority_focused_weights
from SafetyVerifier import SafetyVerifier, SafetyViolation


@dataclass
class ResolutionResult:
    """Result of conflict resolution process."""
    success: bool
    iterations: int
    resolutions_applied: int
    remaining_violations: int
    resolution_chain: List[dict]
    final_timetable: Timetable


def _resolve_spawn_conflicts(timetable, priorities: Dict[int, float], verbose: bool = True):

    from SafetyVerifier import SafetyVerifier

    verifier = SafetyVerifier(timetable, max_steps=10)  # Only check early steps
    _, violations = verifier.verify_safety(verbose=False)

    # Find pairs with very early conflicts (steps 1-3 = spawn zone)
    early_pairs = set()
    for v in violations:
        if v.timestep <= 3:
            pair = (min(v.train_a, v.train_b), max(v.train_a, v.train_b))
            early_pairs.add(pair)

    if not early_pairs:
        return 0

    adjustments = 0
    for pair in early_pairs:
        a, b = pair
        pri_a = priorities.get(a, 1.0)
        pri_b = priorities.get(b, 1.0)

        # Delay the lower priority train
        train_to_delay = b if pri_a >= pri_b else a
        schedule = timetable.get_schedule(train_to_delay)

        # Push departure back by 3 steps
        delay = 3
        schedule.planned_departure += delay
        schedule.planned_arrival += delay
        if getattr(schedule, 'hold_until', None):
            schedule.hold_until += delay

        adjustments += 1
        if verbose:
            print(f"   Spawn conflict {a} vs {b}: delayed Train {train_to_delay} "
                  f"departure by +{delay} (now departs at step {schedule.planned_departure})")

    return adjustments


def generate_resolution_id(option, conflict=None) -> str:
    """
    Generate a stable, human-readable ID for a resolution option.

    IDs are content-based so they remain consistent across re-runs:
      WAIT:    WAIT_T{id}_at_({r},{c})
      REROUTE: REROUTE_T{id}_len{n}_h{hash6}

    Use these IDs in scenario 'rejected_resolutions' sets to block
    specific options without affecting others.
    """
    tid = option.train_to_delay
    if option.resolution_type == ResolutionType.WAIT:
        cell = option.wait_at_cell
        if cell:
            return f"WAIT_T{tid}_at_({cell[0]},{cell[1]})"
        elif conflict:
            return f"WAIT_T{tid}_at_({conflict.cell[0]},{conflict.cell[1]})"
        return f"WAIT_T{tid}"
    else:
        route = option.new_route or []
        h = format(abs(hash(tuple(route))) % 0xFFFFFF, '06X')
        return f"REROUTE_T{tid}_len{len(route)}_h{h}"


def resolve_all_conflicts_safe(
    env,
    timetable,
    priorities,
    train_infos=None,
    max_iterations=50,
    verbose=True,
    stagger_spawn=True,
    rejected_resolutions=None,
):
    """
    rejected_resolutions: optional set of resolution keys to skip.
    Each key is a tuple: (train_a, train_b, resolution_type_str, route_hash)
    where train_a < train_b, resolution_type_str is 'wait' or 'reroute',
    and route_hash = hash(tuple(new_route)) for reroutes or 0 for waits.

    Example — reject the WAIT between trains 0 and 3:
        rejected_resolutions={(0, 3, 'wait', 0)}

    This forces the resolver to find the next-best option (e.g. a reroute).
    """
    if verbose:
        print("\n" + "=" * 70)
        print(" SAFE CONFLICT RESOLUTION")
        print("=" * 70)

    resolution_chain = []
    iteration = 0
    # Pre-populate with any caller-specified rejections so they are
    # skipped as if already attempted.
    attempted_resolutions = set(rejected_resolutions) if rejected_resolutions else set()

    # Pre-pass: spawn staggering
    if verbose:
        print("\n Pre-pass: checking for spawn conflicts (step 1-3)...")
    if stagger_spawn:
        spawn_fixes = _resolve_spawn_conflicts(timetable, priorities, verbose=verbose)
        if verbose:
            if spawn_fixes:
                print(f"   Fixed {spawn_fixes} spawn conflict(s) by staggering departures.")
            else:
                print("   No spawn conflicts found.")
    else:
        if verbose:
            print("   Spawn staggering disabled for this scenario.")

    # Direction fix BEFORE conflict detection so hold_at_cell is computed
    # on the actual route that will be executed.
    _fix_rerouted_route_directions(env, timetable, verbose=verbose)

    # Main resolution loop
    while iteration < max_iterations:
        iteration += 1
        verifier = SafetyVerifier(timetable, max_steps=150)
        is_safe, violations = verifier.verify_safety(verbose=False)
        if is_safe:
            if verbose:
                print(f"\n \u2705 All conflicts resolved after {iteration - 1} iterations!")
            break
        conflicting_pairs = verifier.get_conflicting_pairs()
        if verbose:
            print(f"\n Iteration {iteration}: {len(violations)} violations, {len(conflicting_pairs)} pairs")

        detector = ConflictDetector(env, timetable)
        detected_conflicts, projections = detector.detect_conflicts(0)
        active_ids = set(timetable.schedules.keys())
        detected_conflicts = [c for c in detected_conflicts
                              if c.train_a in active_ids and c.train_b in active_ids]
        projections = {k: v for k, v in projections.items() if k in active_ids}

        resolved_this_iteration = False
        for conflict in detected_conflicts:
            pair = (min(conflict.train_a, conflict.train_b),
                    max(conflict.train_a, conflict.train_b))
            if pair not in conflicting_pairs:
                continue
            generator = ResolutionGenerator(env)
            calculator = CostCalculator(env, timetable, weights=get_priority_focused_weights())
            options = generator.generate_all_options(conflict, priorities, timetable, projections)
            if not options:
                continue
            ranked = calculator.compare_options(options, projections)

            # Print rejected options so user knows what was skipped
            if verbose and rejected_resolutions:
                for opt, _, _ in ranked:
                    rid = generate_resolution_id(opt, conflict)
                    if rid in attempted_resolutions:
                        rn = train_infos[opt.train_to_delay].name if train_infos else f"Train {opt.train_to_delay}"
                        print(f"   [REJECTED] {rid}")

            for option, cost, _ in ranked:
                resolution_key = generate_resolution_id(option, conflict)

                if resolution_key in attempted_resolutions:
                    continue
                schedule = timetable.get_schedule(option.train_to_delay)
                old_route_len = len(schedule.route)
                if option.resolution_type == ResolutionType.REROUTE:
                    schedule.route = option.new_route
                    schedule.planned_arrival += option.delay_added
                    schedule.was_rerouted = True
                    schedule.reroute_delay_added += option.delay_added
                elif option.resolution_type == ResolutionType.WAIT:
                    schedule.planned_arrival += option.delay_added
                    schedule.was_held = True
                    schedule.hold_until = option.wait_until
                    schedule.hold_at_cell = option.wait_at_cell
                    schedule.reroute_delay_added += option.delay_added
                attempted_resolutions.add(resolution_key)
                train_name = train_infos[option.train_to_delay].name if train_infos else f"Train {option.train_to_delay}"
                resolution_chain.append({
                    'iteration': iteration,
                    'train': option.train_to_delay,
                    'train_name': train_name,
                    'type': option.resolution_type.value,
                    'delay': option.delay_added,
                    'conflict_cell': conflict.cell,
                    'old_route_len': old_route_len,
                    'new_route_len': len(schedule.route),
                })
                if verbose:
                    name_a = train_infos[conflict.train_a].name if train_infos else f"Train {conflict.train_a}"
                    name_b = train_infos[conflict.train_b].name if train_infos else f"Train {conflict.train_b}"
                    print(f"   {name_a} vs {name_b} at {conflict.cell}")
                    print(f"   -> {option.resolution_type.value.upper()} {train_name} (+{option.delay_added})")
                    print(f"   ID: {resolution_key}")
                resolved_this_iteration = True
                break
            if resolved_this_iteration:
                break

        if not resolved_this_iteration:
            if verbose:
                print(f"\n \u26a0\ufe0f No more resolution options available!")
                remaining = verifier.get_conflicting_pairs()
                print(f"    Remaining: {len(remaining)} pairs")
                for pr in sorted(remaining)[:5]:
                    na = train_infos[pr[0]].name if train_infos else f"Train {pr[0]}"
                    nb = train_infos[pr[1]].name if train_infos else f"Train {pr[1]}"
                    print(f"       {na} vs {nb}")
            break

    # Final verification
    verifier = SafetyVerifier(timetable, max_steps=150)
    is_safe, final_violations = verifier.verify_safety(verbose=False)

    if verbose:
        print("\n" + "-" * 70)
        print(" RESOLUTION SUMMARY")
        print("-" * 70)
        print(f" Iterations: {iteration}")
        print(f" Resolutions applied: {len(resolution_chain)}")
        safe_str = "✅ SAFE" if is_safe else f"❌ {len(final_violations)} violations"
        print(f" Final safety: {safe_str}")
        if not is_safe:
            remaining_pairs = set()
            for v in final_violations:
                remaining_pairs.add((min(v.train_a, v.train_b), max(v.train_a, v.train_b)))
            print(f"\n Unresolved pairs ({len(remaining_pairs)}):")
            for pr in sorted(remaining_pairs):
                na = train_infos[pr[0]].name if train_infos else f"Train {pr[0]}"
                nb = train_infos[pr[1]].name if train_infos else f"Train {pr[1]}"
                pv = [v for v in final_violations
                      if (v.train_a, v.train_b) == pr or (v.train_b, v.train_a) == pr]
                steps = sorted(set(v.timestep for v in pv))
                print(f"   {na} vs {nb}: steps {steps[0]}-{steps[-1]}")

    # Direction fix again on any newly rerouted routes
    _fix_rerouted_route_directions(env, timetable, verbose=verbose)

    # Final result
    verifier2 = SafetyVerifier(timetable, max_steps=150)
    is_safe2, final_viol2 = verifier2.verify_safety(verbose=False)

    return ResolutionResult(
        success=is_safe2,
        iterations=iteration,
        resolutions_applied=len(resolution_chain),
        remaining_violations=len(final_viol2) if not is_safe2 else 0,
        resolution_chain=resolution_chain,
        final_timetable=timetable,
    )

def _fix_rerouted_route_directions(env, timetable, verbose=True):

    from Corridor_environment import compute_route_bfs
    DELTA_TO_DIR = {(-1,0):0,(0,1):1,(1,0):2,(0,-1):3}
    DIR_NAMES = {0:"N",1:"E",2:"S",3:"W"}
    fixed = 0

    for agent_id, schedule in timetable.schedules.items():
        agent = env.agents[agent_id]


        if agent.position is not None:
            continue

        if not schedule.route or len(schedule.route) < 2:
            continue

        init_dir = int(agent.initial_direction)

        r0, r1 = schedule.route[0], schedule.route[1]
        dr, dc = r1[0]-r0[0], r1[1]-r0[1]
        route_dir = DELTA_TO_DIR.get((dr, dc))
        if route_dir is None:
            continue

        diff = (route_dir - init_dir) % 4
        if diff == 0:
            continue

        if verbose and diff == 2:
            print(f"   Direction fix: Train {agent_id} route starts "
                  f"{DIR_NAMES[route_dir]} but initial_dir={DIR_NAMES[init_dir]} "
                  f"(180° mismatch) — recomputing route")

        start = tuple(schedule.route[0])
        target = tuple(agent.target)
        new_route = compute_route_bfs(
            env, start, target,
            use_transitions=True,
            start_direction=init_dir,
        )

        if new_route:
            old_len = len(schedule.route)
            schedule.route = new_route
            schedule.planned_arrival = schedule.planned_departure + len(new_route)
            fixed += 1
            if verbose:
                print(f"   Train {agent_id}: route recomputed "
                      f"({old_len} -> {len(new_route)} cells)")
        else:
            if verbose:
                print(f"   Train {agent_id}: WARNING no route found with "
                      f"initial_dir={DIR_NAMES[init_dir]}, keeping original")

    if verbose and fixed:
        print(f"   Direction fixes applied: {fixed}")


# ============== TEST: CORRIDOR MAP (original) ==============

def test_safe_resolution_corridor():
    """Test on the handbuilt corridor with named stations."""
    from Corridor_environment import create_corridor_env, compute_route_bfs
    from TrainInfo import TrainType, calculate_priority

    print("\n" + "=" * 70)
    print(" TESTING SAFE RESOLUTION — CORRIDOR MAP")
    print("=" * 70)

    configs = [
        {'id': 0, 'start': 'GENEVA', 'end': 'ZURICH', 'dep': 1,
         'type': TrainType.PASSENGER_EXPRESS, 'passengers': 400, 'name': 'ICE-101'},
        {'id': 1, 'start': 'ZURICH', 'end': 'GENEVA', 'dep': 1,
         'type': TrainType.PASSENGER_EXPRESS, 'passengers': 350, 'name': 'ICE-102'},
        {'id': 2, 'start': 'GENEVA', 'end': 'ZURICH', 'dep': 4,
         'type': TrainType.PASSENGER_LOCAL, 'passengers': 100, 'name': 'RE-201'},
        {'id': 3, 'start': 'ZURICH', 'end': 'GENEVA', 'dep': 5,
         'type': TrainType.PASSENGER_LOCAL, 'passengers': 100, 'name': 'RE-202'},
        {'id': 4, 'start': 'BERN', 'end': 'MILAN', 'dep': 2,
         'type': TrainType.PASSENGER_LOCAL, 'passengers': 150, 'name': 'EC-301'},
        {'id': 5, 'start': 'MILAN', 'end': 'BERN', 'dep': 3,
         'type': TrainType.FREIGHT, 'passengers': 0, 'name': 'Freight'},
    ]

    n_agents = len(configs)
    env, stations, junctions = create_corridor_env(n_agents=n_agents)
    env.reset()

    schedules = {}
    priorities = {}
    train_infos = {}

    for cfg in configs:
        route = compute_route_bfs(env, stations[cfg['start']], stations[cfg['end']],
                                   use_transitions=True)
        schedules[cfg['id']] = TrainSchedule(
            train_id=cfg['id'],
            planned_departure=cfg['dep'],
            planned_arrival=cfg['dep'] + len(route),
            route=route,
        )
        train_info = TrainInfo(
            train_id=cfg['id'],
            name=cfg['name'],
            train_type=cfg['type'],
            passenger_count=cfg['passengers'],
        )
        train_infos[cfg['id']] = train_info
        priorities[cfg['id']] = calculate_priority(train_info)

    timetable = Timetable(schedules=schedules, priorities=priorities)

    print("\n INITIAL STATE:")
    verifier = SafetyVerifier(timetable, max_steps=100)
    is_safe_before, violations_before = verifier.verify_safety(verbose=False)
    print(f" Collisions before: {len(violations_before)}")

    result = resolve_all_conflicts_safe(
        env, timetable, priorities, train_infos,
        max_iterations=50, verbose=True
    )

    print("\n FINAL VERIFICATION:")
    verifier = SafetyVerifier(timetable, max_steps=100)
    verifier.verify_safety(verbose=True)

    return result


# ============== TEST: LOADED FLATLAND MAP ==============

def test_safe_resolution_loaded(pkl_path: str = "maps/4city_map.pkl"):
    """
    Test safe resolution on any flatland-generated .pkl map.

    Reads agent start/target positions directly from env.agents —
    no hardcoded station names required.

    Args:
        pkl_path: Path to a .pkl file created by Make_map.py
    """
    import os
    from Corridor_environment import load_corridor_env, build_timetable_from_loaded_env

    print("\n" + "=" * 70)
    print(f" TESTING SAFE RESOLUTION — LOADED MAP: {pkl_path}")
    print("=" * 70)

    if not os.path.exists(pkl_path):
        print(f"Map file not found: {pkl_path}")
        print("Run Make_map.py first to generate it.")
        return None

    # Load map — same interface as create_corridor_env()
    env, stations, junctions = load_corridor_env(pkl_path)

    # Build timetable from agent assignments
    timetable, train_infos, priorities = build_timetable_from_loaded_env(env, stations)

    if not timetable.schedules:
        print("No valid schedules built — check route finding.")
        return None

    # Check initial state
    print("\n INITIAL STATE:")
    verifier = SafetyVerifier(timetable, max_steps=150)
    is_safe_before, violations_before = verifier.verify_safety(verbose=False)
    print(f" Collisions before resolution: {len(violations_before)}")

    # Resolve
    result = resolve_all_conflicts_safe(
        env, timetable, priorities, train_infos,
        max_iterations=50, verbose=True
    )

    # Final check
    print("\n FINAL VERIFICATION:")
    verifier = SafetyVerifier(timetable, max_steps=150)
    verifier.verify_safety(verbose=True)

    return result


# ============== ENTRY POINT ==============

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Pass a .pkl path as argument to test a loaded map
        result = test_safe_resolution_loaded(sys.argv[1])
    else:
        # Default: run on the handbuilt corridor
        result = test_safe_resolution_corridor()

    if result:
        print(f"\n\nFinal result: {'SUCCESS' if result.success else 'FAILED'}")