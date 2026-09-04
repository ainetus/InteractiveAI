"""
scenario3.py — Szenario 3: Zugreihenfolge

Karte: maps/map3.json (25x25)

Züge:
    S 17  (Agent 0): Station 3 (16,2)  → Station 4 (2,17)   dir=0 (Nord)
    S 18  (Agent 1): Station 1 (6,23)  → Station 3 (16,2)   dir=3 (West)
    IC 3  (Agent 2): Station 2 (15,10) → Station 4 (2,17)   dir=0 (Nord)
"""

SCENARIO_3 = {
    "id":   "scenario3",
    "name": "Szenario 3 — Zugreihenfolge",
    "map":  "maps/map3.json",

    "agent_defs": [
        dict(start=(16, 2),  target=(2, 17), dir=0, dep=1,  arr=60, name="S 17"),
        dict(start=(6,  23), target=(16, 2), dir=3, dep=22, arr=77, name="S 18"),
        dict(start=(15, 10), target=(2, 17), dir=0, dep=33, arr=68, name="IC 3"),
    ],

    # Co-learning: all 3 trains selectable, vorfahrt=priority, warten=invalid
    "colearning_config": {
        "trains":          ["Train_0", "Train_1", "Train_2"],
        "actions":         ["vorfahrt", "warten"],
        "invalid_actions": ["warten"],
    },

    # Marey link: start=Station1/S17-start (right end), end=Station4 (left end)
    "marey_link": {"start": [16, 2], "end": [2, 17]},

    "events": [
        {
            "timestep":         14,
            "type":             "train_delay",
            "train":            "Train_0",
            "duration":         30,
            "card_title":       "Betriebsstörung — S 17",
            "card_description": (
                "Auf der Strecke wurde ein Hindernis gemeldet. "
                "S 17 muss an der aktuellen Position anhalten und den Streckenabschnitt sichern. "
                "Geschätzte Wartezeit: 30 Zeitschritte. "
                "Der Streckenunterhaltsdienst wurde verständigt."
            ),
        },
        {
            "timestep":         25,
            "type":             "train_delay",
            "train":            "Train_1",
            "duration":         18,
            "card_title":       "Signalstörung — S 18",
            "card_description": (
                "Im Streckenabschnitt von S 18 wurde eine Signalstörung gemeldet. "
                "Der Zug muss gemäss Vorschrift auf Sicht fahren und an der nächsten "
                "Haltestelle auf Freigabe warten. "
                "Geschätzte Verzögerung: 18 Zeitschritte."
            ),
        },
        {
            "timestep":         40,
            "type":             "info",
            "train":            "Train_0",
            "duration":         0,
            "push_card":        True,
            "card_title":       "Dispositionskonflikt — Zugreihenfolge",
            "card_description": (
                "Durch die Verspätungen von S 17 und S 18 ist die geplante Zugreihenfolge "
                "nicht mehr einzuhalten. Bitte entscheiden Sie, welchem Zug Vorfahrt "
                "gewährt werden soll."
            ),
        },
    ],

    "decision_points": [
        {
            "timestep":    40,
            "description": (
                "Aufgrund der Verspätungen von S 17 und S 18 ist die geplante "
                "Zugreihenfolge im gemeinsamen Streckenabschnitt nicht mehr einzuhalten. "
                "Bitte entscheiden Sie, welchem Zug Vorfahrt gewährt werden soll."
            ),
            "options": [
                {
                    "label": "S 18 Vorfahrt — S 17 und IC 3 warten",
                    "kpis": {
                        "local_delay":  33,
                        "global_delay": 25,
                        "energy":       76,
                        "anschluss":    3,
                    },
                    "outcome": {
                        "holds": {
                            "Train_0": 18,   # S17 wartet 18 Schritte
                            "Train_2": 22,   # IC3 wartet 22 Schritte
                        },
                        "scripted_actions": {
                            "Train_1": [2]*14 + [3, 3, 3, 3, 3] + [2]*60,  # try right steps 54-58
                        },
                    },
                },
                {
                    "label": "IC 3 Vorfahrt — S 17 folgt nach 5, S 18 wartet",
                    "kpis": {
                        "local_delay":  28,
                        "global_delay": 20,
                        "energy":       80,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "holds": {
                            "Train_0": 5,    # S17 wartet 5 Schritte
                            "Train_1": 18,   # S18 wartet 18 Schritte
                        }
                    },
                },
                {
                    "label": "S 17 Vorfahrt — S 18 wartet, IC 3 wartet",
                    "kpis": {
                        "local_delay":  35,
                        "global_delay": 28,
                        "energy":       72,
                        "anschluss":    3,
                    },
                    "outcome": {
                        "holds": {
                            "Train_1": 15,   # S18 wartet 15 Schritte
                            "Train_2": 29,   # IC3 wartet 29 Schritte
                        }
                    },
                },
            ],
        }
    ],
}
