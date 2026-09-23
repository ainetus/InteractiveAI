"""
test_scenario.py — Testszenario: Technische Störung (Zug 3)

Ablauf:
    Schritt 15: Technische Störung Zug 3 — Zug 3 wird angehalten.
    Schritt 30: Störung behoben — Zug 3 kann weiterfahren.
                Entscheidungspunkt: Konflikt mit Zug 0 muss gelöst werden.
"""

TEST_SCENARIO = {
    "id":             "test",
    "name":           "Testszenario — Technische Störung",
    "map":            "maps/4city_map.pkl",
    "scenario_index": 0,

    "events": [
        {
            "timestep":         1,
            "type":             "train_delay",
            "train":            "Train_2",
            "duration":         999,
            "push_card":        False,
        },
        {
            "timestep":         15,
            "type":             "train_delay",
            "train":            "Train_3",
            "duration":         15,
            "card_title":       "Technische Störung — Zug 3",
            "card_description": (
                "Zug 3 hat eine technische Störung und wurde angehalten. "
                "Der Wartungstrupp wurde alarmiert. "
                "Voraussichtliche Behebung: 15 Zeitschritte."
            ),
        },
        {
            "timestep":         30,
            "type":             "info",
            "train":            "Train_3",
            "duration":         0,
            "card_title":       "Zug 3 — Technische Störung behoben",
            "card_description": (
                "Die technische Störung von Zug 3 wurde behoben. "
                "Zug 3 ist wieder fahrbereit. "
                "Zug 0 nähert sich demselben Streckenabschnitt — "
                "bitte eine Lösung auswählen, um eine Kollision zu vermeiden."
            ),
        },
    ],

    "decision_points": [
        {
            "timestep": 30,
            "description": (
                "Zug 3 ist nach der technischen Störung wieder fahrbereit. "
                "Zug 0 nähert sich demselben Streckenabschnitt — "
                "ohne Eingriff kommt es zur Kollision. "
                "Bitte eine Lösung auswählen."
            ),
            "options": [
                {
                    "label": "Zug 0 für 15 Schritte anhalten — Zug 3 fährt zuerst",
                    "kpis": {
                        "local_delay":  15,
                        "global_delay": 20,
                        "energy":       76,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "hold_train":  "Train_0",
                        "hold_steps":  15,
                    }
                },
                {
                    "label": "Zug 3 weitere 15 Schritte anhalten — Zug 0 fährt zuerst",
                    "kpis": {
                        "local_delay":  15,
                        "global_delay": 12,
                        "energy":       81,
                        "anschluss":    1,
                    },
                    "outcome": {
                        "hold_train":  "Train_3",
                        "hold_steps":  15,
                    }
                },
                {
                    "label": "Zug 3 über Alternativroute (links) umleiten",
                    "kpis": {
                        "local_delay":  22,
                        "global_delay": 16,
                        "energy":       63,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "scripted_actions": {
                            "Train_3": [2, 2, 2, 2, 2, 2, 2, 1, 1, 1] + [2] * 60,
                        }
                    }
                },
            ]
        }
    ]
}
