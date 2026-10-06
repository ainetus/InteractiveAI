"""
scenario3.py — Güterverkehr vs Personenverkehr

Karte: maps/map3.json (15x20)

Stationen:
    Station 1: (7, 2)  — alle Züge Start
    Station 2: (7, 17) — alle Züge Ziel

Züge:
    Train0 = G 3:   dep=1  speed=0.5 (immer halbe Geschwindigkeit)
    Train1 = IC 3:  dep=6
    Train2 = IR 35: dep=8

Entscheidungspunkt bei Timestep 12:
    Option 1: IC 3 + IR 35 folgen G 3 mit halber Geschwindigkeit.
    Option 2: G 3 biegt links ab (~Step 12), IC 3 + IR 35 überholen normal.
"""

SCENARIO_3 = {
    "id":   "scenario3",
    "name": "Szenario 3 — Güterverkehr vs Personenverkehr",
    "map":  "maps/map3.json",
    "marey_link": {"start": [7, 1], "end": [7, 18]},

    "events": [
        {
            "timestep":         16,
            "type":             "info",
            "train":            "Train_0",
            "duration":         0,
            "push_card":        True,
            "card_title":       "Dispositionskonflikt — G 3 fährt langsam",
            "card_description": (
                "G 3 fährt mit halber Geschwindigkeit. "
                "IC 3 und IR 35 nähern sich von hinten. "
                "Entscheiden Sie, ob die Schnellzüge überholen oder folgen sollen."
            ),
        },
    ],

    "agent_defs": [
        dict(start=(7, 2), target=(7, 17), dir=1, dep=1, arr=40, name="G 3",    speed=0.5),
        dict(start=(7, 2), target=(7, 17), dir=1, dep=12, arr=34, name="IC 3"),
        dict(start=(7, 2), target=(7, 17), dir=1, dep=14, arr=36, name="IR 35"),
    ],

    "decision_points": [
        {
            "timestep":    16,
            "description": (
                "G 3 fährt mit halber Geschwindigkeit und blockiert den Streckenabschnitt. "
                "Wie soll disponiert werden?"
            ),
            "options": [
                {
                    "label": "IC 3 + IR 35 folgen G 3 mit halber Geschwindigkeit",
                    "kpis": {
                        "local_delay":  20,
                        "global_delay": 18,
                        "energy":       85,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "scripted_actions": {
                            "Train_1": [4, 2] * 30,
                            "Train_2": [4, 2] * 30,
                        },
                    },
                },
                {
                    "label": "G 3 weicht aus — IC 3 überholt, G 3 fährt vor IR 35",
                    "kpis": {
                        "local_delay":  12,
                        "global_delay": 7,
                        "energy":       74,
                        "anschluss":    1,
                    },
                    "outcome": {
                        "scripted_actions": {
                            # G 3 biegt links ab (selbe wie Option C)
                            "Train_0": [4, 2, 4, 1, 1, 1, 1] + [4, 2] * 26,
                            # IR 35 wartet 6 Schritte bei Timestep 26 (Index 10 von Decision Step 16)
                            "Train_2": [2] * 10 + [4] * 6 + [2] * 50,
                        },
                        # IC 3 fährt normal weiter
                    },
                },
                {
                    "label": "G 3 weicht aus — IC 3 + IR 35 überholen",
                    "kpis": {
                        "local_delay":  8,
                        "global_delay": 4,
                        "energy":       72,
                        "anschluss":    0,
                    },
                    "outcome": {
                        "scripted_actions": {
                            "Train_0": [4, 2, 4, 1, 1, 1, 1] + [4, 2] * 26,
                        },
                        # IC 3 + IR 35 fahren normal weiter
                    },
                },
            ],
        },
    ],

    "colearning_config": {
        "trains":          ["Train_0", "Train_1", "Train_2"],
        "actions":         ["vorfahrt"],
        "invalid_actions": [],
        "train_labels": {
            "Train_0": "G 3 vorne",
            "Train_1": "IC 3 dann G 3",
            "Train_2": "IC 3 dann IR 35",
        },
    },
}
