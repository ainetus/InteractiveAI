"""
scenario2.py — Szenario 2: Fahrt auf Sichtweite

Karte: maps/map2.json (25×25)

Züge (alle Richtung Norden, dir=0):
    P 205 (Agent 0): Station 1 (17,2)  → Station 4 (6,22)  dep=1
    G 501 (Agent 1): Station 2 (15,12) → Station 5 (1,6)   dep=15
    P 312 (Agent 2): Station 3 (15,22) → Station 5 (1,6)   dep=12  (+3 früher)

Konfliktzone: Row 7 (P205 fährt ost, G501/P312 fahren west)
"""

SCENARIO_2 = {
    "id":   "scenario2",
    "name": "Szenario 2 — Fahrt auf Sichtweite",
    "map":  "maps/map2.json",

    "agent_defs": [
        dict(start=(17, 2),  target=(6,  22), dir=0, dep=1,  arr=80, name="P 205"),
        dict(start=(15, 12), target=(1,   6), dir=0, dep=15, arr=80, name="G 501"),
        dict(start=(15, 22), target=(1,   6), dir=0, dep=12, arr=85, name="P 312"),
    ],

    "colearning_config": {
        "trains":          ["Train_0", "Train_1", "Train_2"],
        "actions":         ["vorfahrt", "warten"],
        "invalid_actions": ["warten"],
    },

    "events": [
        {
            "timestep":         5,
            "type":             "train_delay",
            "train":            "Train_0",
            "duration":         8,
            "card_title":       "Streckenkontrolle — Vmax 40 km/h",
            "card_description": (
                "Im Bereich Rüthi wurde eine Unregelmässigkeit der Fahrbahn festgestellt. "
                "Für P 205 gilt Vmax 40 km/h. Fachdienst wurde aufgeboten."
            ),
        },
        {
            "timestep":         22,
            "type":             "info",
            "train":            "Train_0",
            "duration":         0,
            "card_title":       "Dispositionskonflikt — Kreuzungsreihenfolge",
            "card_description": (
                "P 205 ist verspätet und verursacht einen Kreuzungskonflikt "
                "mit G 501 und P 312 auf dem Einspurabschnitt. "
                "Bitte legen Sie die Zugreihenfolge fest."
            ),
        },
    ],

    "decision_points": [
        {
            "timestep":    22,
            "description": (
                "Durch die Geschwindigkeitsreduktion auf dem Streckenabschnitt "
                "ist die ursprünglich geplante Kreuzungsreihenfolge nicht mehr möglich. "
                "Welchem Zug soll Vorfahrt gewährt werden?"
            ),
            "options": [
                {
                    "label": "P 205 Vorfahrt — G 501 und P 312 warten",
                    "kpis": {
                        "local_delay":  20,  # G501+P312 je ~10 min
                        "global_delay": 14,
                        "energy":       78,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "hold_trains": ["Train_1", "Train_2"],
                        "hold_steps":  10,
                    }
                },
                {
                    "label": "G 501 Vorfahrt — P 205 und P 312 warten",
                    "kpis": {
                        "local_delay":  29,  # P205 10 min + P312 19 min
                        "global_delay": 20,
                        "energy":       72,
                        "anschluss":    3,
                    },
                    "outcome": {
                        "holds": {
                            "Train_0": 10,
                            "Train_2": 19,  # 9 Schritte mehr als Train_0
                        }
                    }
                },
                {
                    "label": "P 312 Vorfahrt — P 205 und G 501 warten",
                    "kpis": {
                        "local_delay":  28,  # P205 18 min + G501 10 min
                        "global_delay": 23,
                        "energy":       70,
                        "anschluss":    3,
                    },
                    "outcome": {
                        "holds": {
                            "Train_0": 18,  # 8 Schritte mehr für Train_0
                            "Train_1": 10,
                        }
                    }
                },
            ],
        }
    ],
}
