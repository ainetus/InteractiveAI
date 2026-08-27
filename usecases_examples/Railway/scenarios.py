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
# SCENARIO DEFINITIONS
# ============================================================

def make_scenarios(env, stations, train_infos=None):
    from copy import deepcopy
    from Corridor_environment import build_timetable_from_loaded_env
    from TrainInfo import TrainType, calculate_priority

    base_timetable, base_train_infos, base_priorities = build_timetable_from_loaded_env(
        env, stations, departure_offset=1, stagger_departures=True
    )

    def clone_timetable(base, agent_ids=None, new_departures=None):
        t = deepcopy(base)
        if agent_ids is not None:
            for aid in list(t.schedules.keys()):
                if aid not in agent_ids:
                    del t.schedules[aid]
                    t.priorities.pop(aid, None)
        if new_departures:
            for aid, dep in new_departures.items():
                if aid in t.schedules:
                    s = t.schedules[aid]
                    route_len = len(s.route)
                    s.planned_departure = dep
                    s.planned_arrival = dep + route_len
                    s.original_planned_arrival = dep + route_len
        return t

    ids_all     = sorted(base_timetable.schedules.keys())
    agent_count = len(ids_all)
    ti = base_train_infos
    p  = base_priorities

    scenarios = []

    # ── Scenario 1: junction wait — no random delays ──────────────────────
    if agent_count >= 2:
        a0, a_last = ids_all[0], ids_all[-1]
        deps = {aid: 1 + i * 2 for i, aid in enumerate(ids_all)}
        deps[a0]     = 1
        deps[a_last] = 1
        scenarios.append({
            'name': 'Scenario 1: 4 trains, junction wait conflict',
            'description': (
                f'Train {a0} departs step 1, Train {a_last} departs step 9, others staggered. '
                'Creates a junction waiting conflict that the resolver must handle. '
                'No random delays — pure conflict resolution.'
            ),
            'timetable': clone_timetable(base_timetable, new_departures=deps),
            'train_infos': ti, 'priorities': p,
            'stagger_spawn': False,
            'enable_random_delays': False,
            'delay_probability': 0.0,
        })

    # ── Scenario 2: junction wait — with random delays ────────────────────
    if agent_count >= 2:
        a0, a_last = ids_all[0], ids_all[-1]
        deps = {aid: 1 + i * 2 for i, aid in enumerate(ids_all)}
        deps[a0]     = 1
        deps[a_last] = 9
        scenarios.append({
            'name': 'Scenario 2: 4 trains, junction wait conflict with random delays',
            'description': (
                'Same as Scenario 1 but with random delay injection enabled. '
                'Each train has a 15% chance of a delay event (5–30 steps). '
                'Watch the Injected column in the schedule table.'
            ),
            'timetable': clone_timetable(base_timetable, new_departures=deps),
            'train_infos': ti, 'priorities': p,
            'stagger_spawn': False,
            'enable_random_delays': True,
            'delay_probability': 0.15,
        })

    # ── Scenario 3: cancel button test ────────────────────────────────────
    a0, a_last = ids_all[0], ids_all[-1]
    deps = {aid: 1 + i * 2 for i, aid in enumerate(ids_all)}
    deps[a_last] = 80

    t3  = clone_timetable(base_timetable, new_departures=deps)
    ti3 = deepcopy(ti)
    if a0 in ti3:
        ti3[a0].train_type      = TrainType.PASSENGER_EXPRESS
        ti3[a0].passenger_count = 400
    if a_last in ti3:
        ti3[a_last].train_type      = TrainType.FREIGHT
        ti3[a_last].passenger_count = 0
    p3 = {aid: calculate_priority(ti3[aid]) for aid in ti3}
    t3.priorities = p3

    scenarios.append({
        'name': 'Scenario 3: cancel button test scenario',
        'description': (
            f'Train {a0} is a high-priority express (dep=1). '
            f'Train {a_last} is a freight train that departs very late (dep=80). '
            f'Select Train {a_last} in the schedule table before step 80 '
            f'and click Cancel Train to test live train removal and re-resolve.'
        ),
        'timetable': t3, 'train_infos': ti3, 'priorities': p3,
        'stagger_spawn': False,
        'enable_random_delays': False,
        'delay_probability': 0.0,
    })

    # ── Scenario 4: Cooperative Learning Demo ─────────────────────────────
    # Identical timetable to Scenario 1 (T0 dep=1, T_last dep=9) so the
    # conflict is known and reproducible. The only difference: the user's
    # manual resolution choice is saved to learned_resolutions.json and
    # pre-applied automatically on every subsequent load.
    if agent_count >= 2:
        a0, a_last = ids_all[0], ids_all[-1]
        deps = {aid: 1 + i * 2 for i, aid in enumerate(ids_all)}
        deps[a0]     = 1
        deps[a_last] = 9
        scenarios.append({
            'name': 'Scenario 4: Cooperative Learning Demo',
            'description': (
                f'Same conflict as Scenario 1: Train {a0} dep=1, Train {a_last} dep=9. '
                'Switch to Manual mode and resolve the conflict — your choice is '
                'saved and replayed automatically every time you reload this scenario.'
            ),
            'timetable': clone_timetable(base_timetable, new_departures=deps),
            'train_infos': deepcopy(ti), 'priorities': deepcopy(p),
            'stagger_spawn': False,
            'enable_random_delays': False,
            'delay_probability': 0.0,
        })

    return scenarios