"""
scenario2.py

Karte: maps/map2.json (15x20)

Stationen:
    Station 1: (8,  1) — Train0 start
    Station 2: (4,  2) — Train2 start
    Station 3: (4, 17) — Train2 ziel
    Station 4: (6, 16) — Train0 ziel
    Station 5: (7, 17) — Train1 start
    Station 6: (2,  5) — Train1 ziel

Züge:
    Train0: Station 1 (8,1)  → Station 4 (6,16)  dir=0 (Nord) dep=1
    Train1: Station 5 (7,17) → Station 6 (2,5)   dir=3 (West) dep=10
    Train2: Station 2 (4,2)  → Station 3 (4,17)  dir=1 (Ost)  dep=14

Konflikt: Entscheidung bei Timestep 15
    Option A: Train1 wartet (Hold 7 Schritte bis Step 23), Train1 biegt bei (6,5) rechts ab
    Option B: Train1 fährt weiter (biegt bei Step 17 rechts ab), Train2 wartet (Hold 12 Schritte bis Step 28)
"""

SCENARIO_2 = {
    "id":   "scenario2",
    "name": "Szenario 2 — Türstörung",
    "map":  "maps/map2.json",

    "agent_defs": [
        dict(start=(8,  1), target=(6, 16), dir=0, dep=1,  arr=35, name="S 17"),
        dict(start=(7, 17), target=(2,  5), dir=3, dep=10, arr=35, name="IR 35"),
        dict(start=(4,  2), target=(4, 17), dir=1, dep=13, arr=39, name="S 17-2"),
    ],

    "events": [
        {
            "timestep":         3,
            "type":             "train_delay",
            "train":            "Train_0",
            "duration":         6,
            "push_card":        True,
            "card_title":       "Türstörung — S 17",
            "card_description": (
                "An S 17 wurde eine Türstörung gemeldet. "
                "Der Zug muss an der aktuellen Position anhalten. "
                "Geschätzte Wartezeit: 6 Zeitschritte."
            ),
        },
        {
            "timestep":         15,
            "type":             "info",
            "train":            "Train_1",
            "duration":         0,
            "push_card":        True,
            "card_title":       "Dispositionskonflikt — Entscheidung erforderlich",
            "card_description": (
                "Infolge der Türstörung von Train 0 kommt es zu einem Engpass. "
                "IR 35 und S 17-2 nähern sich dem gemeinsamen Abschnitt gleichzeitig. "
                "Bitte entscheiden Sie, welchem Zug Vorfahrt gewährt werden soll."
            ),
        },
    ],

    "decision_points": [
        {
            "timestep":    15,
            "description": (
                "IR 35 und S 17-2 nähern sich gleichzeitig einem eingleisigen Abschnitt. "
                "Entscheiden Sie, welcher Zug zuerst passiert."
            ),
            "options": [
                {
                    "label": "IR 35 wartet — S 17-2 passiert zuerst",
                    "kpis": {
                        "local_delay":  14,
                        "global_delay": 8,
                        "energy":       78,
                        "anschluss":    1,
                    },
                    "outcome": {
                        "holds": {"Train_1": 8},   # wartet bis Step 23
                        "scripted_actions": {
                            # DO_NOTHING for hold (indices 0-7), then forward, right at step 31 (index 16)
                            # Try adjusting last [2]*8 count to shift right turn between steps 30-33
                            "Train_1": [4]*8 + [2]*8 + [3, 3, 3] + [2]*50,  # try right at steps 31,32,33
                        },
                    },
                },
                {
                    "label": "IR 35 weiterfahren — S 17-2 wartet",
                    "kpis": {
                        "local_delay":  24,
                        "global_delay": 14,
                        "energy":       72,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "holds": {"Train_2": 13},   # wartet bis Step 28
                        "scripted_actions": {
                            # Train 1 biegt bei Step 17 (Index 1) rechts ab
                            "Train_1": [2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 3] + [2]*50,  # rechts bei Step 17 (Index 2) und Step 26 (Index 11)
                        },
                    },
                },
            ],
        },
    ],

    "colearning_config": {
        "trains":          ["Train_1", "Train_2"],
        "actions":         ["vorfahrt", "warten"],
        "invalid_actions": ["warten"],
    },
}
