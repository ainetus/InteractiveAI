"""Toggles for run_scenario.py (hardcoded on purpose, no command line)."""

SCENARIO_ID = "scenario1"        # one of experiment_scenarios.ALL_SCENARIOS, or None = whole session
PARTICIPANT = "TEST"             # pseudonym; also seeds the scenario order of a session
MODE = "recommendation"          # "recommendation" or "colearning"

# Stand-in for the operator's choice at every decision point
OPTION_INDEX = 0                 # recommendation mode
COLEARNING_TRAIN = "Train_0"     # colearning mode
COLEARNING_ACTION = "vorfahrt"   # "vorfahrt" | "warten" | "umleiten"

PRINT_PAYLOADS = False           # print the draft InteractiveAI payloads (event/context/recommendations)
PRINT_DISPATCH_EVENTS = False    # print dispatcher events (departed, blocked, arrived, ...)
