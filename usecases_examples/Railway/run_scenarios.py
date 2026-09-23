"""
run_scenarios.py — Test runner for loaded Flatland maps.
"""

import argparse
import os
from typing import Dict, List

from Corridor_environment import load_corridor_env, build_timetable_from_loaded_env
from Timetable import Timetable, TrainSchedule
from TrainInfo import TrainInfo, TrainType, calculate_priority
from SafetyVerifier import SafetyVerifier
from safe_resolver import resolve_all_conflicts_safe
from FlatlandMapLoader import visualize_loaded_env
from scenarios import make_scenarios


# ============================================================
# SCENARIO RENDERER
# ============================================================

class ScenarioRenderer:
    def __init__(self, env):
        self.env = env
        self.renderer = None
        self.fig = None
        self.ax = None
        self.img_artist = None
        self._available = False
        self._init_renderer()

    def _init_renderer(self):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
        except Exception:
            pass
        try:
            import matplotlib.pyplot as plt
            from flatland.utils.rendertools import RenderTool
            self.renderer = RenderTool(self.env, gl="PILSVG",
                                       screen_width=800, screen_height=600)
            plt.ion()
            self.fig, self.ax = plt.subplots(figsize=(10, 7))
            self.ax.axis("off")
            self.fig.tight_layout(pad=0)
            self._plt = plt
            self._available = True
            plt.show(block=False)
            plt.pause(0.1)
            print("  Renderer: matplotlib window ready.")
        except Exception as e:
            print(f"  Renderer: unavailable ({e}). Using ASCII fallback.")

    @property
    def available(self):
        return self._available

    def render_frame(self, step: int, pause: float = 0.3):
        if not self._available:
            return
        try:
            image = self.renderer.render_env(
                show=False, show_observations=False,
                show_inactive_agents=True, show_rowcols=True,
                return_image=True,
            )
            if image is None:
                return
            if self.img_artist is None:
                self.img_artist = self.ax.imshow(image)
            else:
                self.img_artist.set_data(image)
            self.ax.set_title(f"Step {step}", fontsize=11)
            self.fig.canvas.draw()
            self.fig.canvas.flush_events()
            self._plt.pause(pause)
        except Exception as e:
            print(f"  Render error at step {step}: {e}")
            self._available = False

    def close(self):
        if self._available:
            try:
                self._plt.ioff()
                self._plt.close(self.fig)
            except Exception:
                pass




# ============================================================
# SCENARIO RUNNER
# ============================================================

def run_scenario(
    scenario: Dict,
    env,
    stations: Dict,
    junctions: List,
    render: bool = False,
    pause: float = 0.3,
    max_steps: int = 150,
    verbose: bool = True,
    ignore_holds: bool = False,
    rejected_resolutions=None,
    enable_random_delays: bool = False,
    delay_probability: float = 0.15,
) -> Dict:
    name        = scenario['name']
    timetable   = scenario['timetable']
    train_infos = scenario['train_infos']
    priorities  = scenario['priorities']

    # CLI flags override scenario defaults
    use_delays  = enable_random_delays or scenario.get('enable_random_delays', False)
    delay_prob  = delay_probability    if enable_random_delays else scenario.get('delay_probability', 0.15)

    print(f"\n{'='*70}")
    print(f" SCENARIO: {name}")
    print(f"{'='*70}")
    print(f" {scenario['description']}")
    print(f" Trains: {len(timetable.schedules)}  |  Random delays: {use_delays}")

    verifier = SafetyVerifier(timetable, max_steps=max_steps)
    is_safe_before, violations_before = verifier.verify_safety(verbose=False)
    print(f"\n Pre-resolution:  {'✅ safe' if is_safe_before else f'❌ {len(violations_before)} violations'}")

    result = resolve_all_conflicts_safe(
        env, timetable, priorities, train_infos,
        max_iterations=50, verbose=verbose,
        stagger_spawn=scenario.get('stagger_spawn', False),
        rejected_resolutions=scenario.get('rejected_resolutions', None),
    )

    verifier2 = SafetyVerifier(timetable, max_steps=max_steps)
    is_safe_after, violations_after = verifier2.verify_safety(verbose=False)
    print(f"\n Post-resolution: {'✅ safe' if is_safe_after else f'❌ {len(violations_after)} violations'}")

    print("\n Final schedule after resolution:")
    for tid, sched in sorted(timetable.schedules.items()):
        hold_str   = ""
        if getattr(sched, 'was_held', False) and getattr(sched, 'hold_until', None):
            hold_str = f", HOLD at {getattr(sched,'hold_at_cell',None)} until step {sched.hold_until}"
        reroute_str = " [REROUTED]" if getattr(sched, 'was_rerouted', False) else ""
        print(f"   Train {tid}: dep={sched.planned_departure}, "
              f"route_len={len(sched.route)}{hold_str}{reroute_str}")

    print()
    visualize_loaded_env(env, stations, junctions, step=0)

    _simulate_and_render(env, timetable, train_infos, priorities, stations, junctions,
                          max_steps=max_steps, pause=pause,
                          ignore_holds=ignore_holds,
                          enable_random_delays=use_delays,
                          delay_probability=delay_prob,
                          render=render)

    return {
        'name': name,
        'n_trains': len(timetable.schedules),
        'violations_before': len(violations_before),
        'violations_after': len(violations_after),
        'success': is_safe_after,
        'iterations': result.iterations,
        'resolutions': result.resolutions_applied,
    }


# ============================================================
# SIMULATE AND RENDER
# ============================================================

def _simulate_and_render(env, timetable, train_infos, priorities, stations, junctions,
                          max_steps=150, pause=0.3, ignore_holds=False,
                          enable_random_delays=False, delay_probability=0.15,
                          render=True):
    from TimetableDispatcher import TimetableDispatcher

    print("\n Rendering simulation...")
    env.reset()

    for agent_id in range(len(env.agents)):
        agent    = env.agents[agent_id]
        schedule = timetable.schedules.get(agent_id)
        dep = schedule.planned_departure if schedule else 9999
        if hasattr(agent, 'earliest_departure'):
            agent.earliest_departure = dep
        if hasattr(env, 'timetable') and env.timetable is not None:
            try:
                env.timetable.earliest_departures[agent_id][0] = dep
            except Exception:
                pass

    dispatcher = TimetableDispatcher(
        env, timetable,
        ignore_holds=ignore_holds,
        train_infos=train_infos,
        enable_random_delays=enable_random_delays,
        delay_probability=delay_probability,
        delay_min_steps=5,
        delay_max_steps=30,
    )
    dispatcher.reset()
    renderer = ScenarioRenderer(env) if render else None

    dispatcher.print_timetable_plan(train_infos=train_infos)

    if renderer is None or not renderer.available:
        for step in range(1, max_steps + 1):
            actions = dispatcher.get_actions(step)
            _, _, dones, _ = env.step(actions)
            for evt in dispatcher.get_step_events():
                if evt.event_type in ('departed', 'arrived', 'holding_at_cell',
                                       'delay_injected', 'deadlock_warning'):
                    print(f"  {evt}")
            if dispatcher.get_pending_replan():
                print(f"\n  [Re-planning at step {step}...]")
                resolve_all_conflicts_safe(
                    env, timetable, priorities, train_infos,
                    max_iterations=20, verbose=False, stagger_spawn=False)
                dispatcher._init_routes(preserve_active=True)
                print(f"  [Re-plan complete]")
            if dones.get('__all__', False):
                print(f"  All agents done at step {step}.")
                break
        dispatcher.print_final_report(train_infos=train_infos)
        _print_delay_summary(timetable, train_infos)
        return

    if render and renderer and renderer.available:
        renderer.render_frame(step=0, pause=pause)

    for step in range(1, max_steps + 1):
        actions = dispatcher.get_actions(step)
        _, _, dones, _ = env.step(actions)

        if render and renderer and renderer.available:
            active  = [i for i, a in enumerate(env.agents)
                       if a.position is not None and i in timetable.schedules]
            pending = [i for i in sorted(timetable.schedules)
                       if env.agents[i].position is None
                       and not timetable.schedules[i].planned_departure <= step]
            renderer.ax.set_title(
                f"Step {step}  |  Active: {active}  |  Waiting: {pending}",
                fontsize=9)
            renderer.render_frame(step=step, pause=pause)

        for evt in dispatcher.get_step_events():
            if evt.event_type in ('deadlock_warning', 'priority_blocked',
                                   'departed', 'arrived', 'holding_at_cell',
                                   'delay_injected'):
                print(f"  {evt}")

        if dispatcher.get_pending_replan():
            print(f"\n  [Re-planning after injected delay at step {step}...]")
            resolve_all_conflicts_safe(
                env, timetable, priorities, train_infos,
                max_iterations=20, verbose=False, stagger_spawn=False)
            dispatcher._init_routes(preserve_active=True)
            print(f"  [Re-plan complete]")

        if dones.get('__all__', False):
            print(f"  All agents done at step {step}.")
            break

    dispatcher.print_final_report(train_infos=train_infos)
    _print_delay_summary(timetable, train_infos)
    if renderer:
        renderer.close()
    print(" Render complete.")


# ============================================================
# DELAY SUMMARY
# ============================================================

def _print_delay_summary(timetable, train_infos):
    print("\n" + "=" * 70)
    print(" DELAY SUMMARY")
    print("=" * 70)
    print(f"  {'Train':<30} {'PlannedArr':>10} {'ActualArr':>10} "
          f"{'TotalDelay':>11} {'RerouteDelay':>13} {'InjectedDelay':>14}")
    print("  " + "-" * 68)
    any_delay = False
    for tid, s in sorted(timetable.schedules.items()):
        name     = train_infos[tid].name if tid in train_infos else f"Train {tid}"
        planned  = s.original_planned_arrival
        actual   = s.actual_arrival if s.actual_arrival is not None else "—"
        total    = s.arrival_delay  if s.arrival_delay  is not None else "—"
        reroute  = s.reroute_delay_added
        injected = s.injected_delay_steps
        status   = (" [incomplete]" if s.actual_arrival is None
                    else " ✓" if s.is_on_time else " ✗")
        if not s.is_on_time and s.actual_arrival is not None:
            any_delay = True
        actual_str = str(actual) if actual != "—" else "—"
        total_str  = f"+{total}" if isinstance(total, int) and total > 0 else str(total)
        print(f"  {name:<30} {planned:>10} {actual_str:>10} "
              f"{total_str:>11} {reroute:>13} {injected:>14}{status}")
    print("  " + "-" * 68)
    print(f"  Weighted delay (Σ delay×priority): {timetable.weighted_delay():.1f}")
    if not any_delay:
        print("  All trains on time ✓")
    print("=" * 70)


# ============================================================
# SUMMARY PRINTER
# ============================================================

def print_summary(results: List[Dict]):
    print(f"\n{'='*70}")
    print(" SCENARIO SUMMARY")
    print(f"{'='*70}")
    print(f"{'#':<3} {'Scenario':<40} {'Trains':<7} {'Before':<8} "
          f"{'After':<7} {'Res':<5} {'Result'}")
    print("-" * 70)
    for i, r in enumerate(results):
        status = "✅ PASS" if r['success'] else "❌ FAIL"
        print(f"{i:<3} {r['name'][:39]:<40} {r['n_trains']:<7} "
              f"{r['violations_before']:<8} {r['violations_after']:<7} "
              f"{r['resolutions']:<5} {status}")
    passed = sum(1 for r in results if r['success'])
    print(f"\n Passed: {passed}/{len(results)}")


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map",        default="maps/4city_map.pkl")
    parser.add_argument("--render",     action="store_true")
    parser.add_argument("--scenario",   type=int, default=None)
    parser.add_argument("--pause",      type=float, default=0.3)
    parser.add_argument("--steps",      type=int, default=150)
    parser.add_argument("--no-waits",   action="store_true")
    parser.add_argument("--delays",     action="store_true")
    parser.add_argument("--delay-prob", type=float, default=0.15)
    parser.add_argument("--quiet",      action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.map):
        print(f"Map not found: {args.map}")
        return

    print(f"Loading map: {args.map}")
    env, stations, junctions = load_corridor_env(args.map)
    scenarios = make_scenarios(env, stations, train_infos=None)

    if not scenarios:
        print("No scenarios could be built.")
        return

    print(f"\nAvailable scenarios ({len(scenarios)} total):")
    for i, s in enumerate(scenarios):
        delays_tag = " [delays]" if s.get('enable_random_delays') else ""
        print(f"  {i}: {s['name']}{delays_tag}")

    to_run = [args.scenario] if args.scenario is not None else list(range(len(scenarios)))

    results = []
    for idx in to_run:
        if idx >= len(scenarios):
            print(f"Scenario {idx} does not exist.")
            continue
        result = run_scenario(
            scenario=scenarios[idx],
            env=env, stations=stations, junctions=junctions,
            render=args.render, pause=args.pause,
            max_steps=args.steps, verbose=not args.quiet,
            ignore_holds=args.no_waits,
            enable_random_delays=args.delays,
            delay_probability=args.delay_prob,
        )
        results.append(result)

    if len(results) > 1:
        print_summary(results)


if __name__ == "__main__":
    main()