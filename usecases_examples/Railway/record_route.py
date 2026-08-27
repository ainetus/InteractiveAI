"""
record_route.py — Records the action sequence for Train 3 taking the alternate left route.

Run this from the Railway folder:
    python record_route.py

It will:
1. Load the environment (same as the scenario)
2. Run to step 30 with Train 3 held from step 15-29
3. From step 30 onwards, try MOVE_LEFT for Train 3 at every step
4. Let the dispatcher handle all other trains
5. Print the full action sequence for Train 3

Copy the output into test_scenario.py as "scripted_actions" for option C.
"""

import sys
sys.path.insert(0, '.')

from Corridor_environment import load_corridor_env
from TimetableDispatcher import TimetableDispatcher
from ScenarioManager import ScenarioManager

# ── Load environment ───────────────────────────────────────────────────────────
env, stations, junctions = load_corridor_env("maps/4city_map.pkl")
manager    = ScenarioManager(env, stations, junctions)
timetable, train_infos, _ = manager.load_scenario_manual(0)
dispatcher = TimetableDispatcher(
    env, timetable,
    train_infos=train_infos,
    enable_random_delays=False,
)

# Flatland action constants
DO_NOTHING   = 4  # STOP_MOVING
MOVE_LEFT    = 1
MOVE_FORWARD = 2
MOVE_RIGHT   = 3

MAX_STEPS    = 100
HOLD_START   = 15
HOLD_END     = 29   # inclusive
DECISION_STEP = 30

# Track Train 3's actions after decision
train3_actions = []
all_actions_log = []

print("Running simulation...")
print(f"Train 3 holds from step {HOLD_START} to {HOLD_END}")
print(f"From step {DECISION_STEP}: Train 3 takes MOVE_LEFT at every opportunity\n")

for step in range(MAX_STEPS):
    # Get dispatcher actions
    actions = dispatcher.get_actions(step)

    # Hold Train 3 from step 15-29
    if HOLD_START <= step <= HOLD_END:
        actions[3] = DO_NOTHING

    # From step 30: try MOVE_LEFT for Train 3
    if step >= DECISION_STEP:
        actions[3] = MOVE_LEFT
        train3_actions.append(MOVE_LEFT)

    # Step environment
    obs, rewards, dones, info = env.step(actions)

    # Print Train 3 position and action
    a3 = env.agents[3]
    action_taken = actions.get(3, DO_NOTHING)
    if step >= DECISION_STEP:
        action_name = {1: 'LEFT', 2: 'FWD', 3: 'RIGHT', 4: 'STOP', 0: 'NOTHING'}.get(action_taken, '?')
        print(f"Step {step:3d}: Train3 pos={a3.position}, dir={a3.direction}, action={action_name}")

    if dones.get('__all__', False):
        print(f"\nAll trains done at step {step}")
        break

    if a3.position is None and step > DECISION_STEP:
        print(f"\nTrain 3 reached target at step {step}")
        break

print(f"\n{'='*60}")
print("COPY THIS INTO test_scenario.py option C outcome:")
print(f"{'='*60}")
print(f'"scripted_actions": {{')
print(f'    "Train_3": {train3_actions},')
print(f'}}')
print(f"\nTotal actions recorded: {len(train3_actions)}")
