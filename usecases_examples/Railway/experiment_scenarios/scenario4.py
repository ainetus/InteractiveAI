"""
scenario4.py — Verschobene Kreuzung

Karte: maps/map4.json (15x20)

Stationen:
    Station 1: (6, 16) — IR35 Start
    Station 2: (7, 17) — G4 + IC3 Ziel
    Station 5: (9,  0) — G4 + IC3 Start (Northbound)
    Station 4: (6,  2) — IR35 Ziel

Züge:
    Train0 = IR35: Station1 (6,16) → Station4 (6,2)  dir=3 (West) dep=1
    Train1 = G4:   Station3 (7,1)  → Station2 (7,17) dir=1 (Ost)  dep=10
    Train2 = IC3:  Station3 (7,1)  → Station2 (7,17) dir=1 (Ost)  dep=17
"""

SCENARIO_4 = {
    "id":   "scenario4",
    "name": "Szenario 4 — Verschobene Kreuzung",
    "map":  "maps/map4.json",

    "agent_defs": [
        dict(start=(6, 16), target=(6,  2), dir=3, dep=1,  arr=20, name="IR 35"),
        dict(start=(9,  0), target=(7, 17), dir=0, dep=17, arr=38, name="G 4"),
        dict(start=(9,  0), target=(7, 17), dir=0, dep=20, arr=41, name="IC 3"),
    ],

    "events": [
        {
            "timestep":         5,
            "type":             "train_delay",
            "train":            "Train_0",
            "duration":         17,
            "push_card":        True,
            "card_title":       "Signalstörung — IR 35",
            "card_description": (
                "Auf der Strecke von IR 35 wurde eine Signalstörung festgestellt. "
                "Der Zug muss an der aktuellen Position anhalten und auf Freigabe warten. "
                "Geschätzte Wartezeit: 17 Zeitschritte."
            ),
        },
    ],

    "decision_points": [
        {
            "timestep":    22,
            "description": (
                "Infolge der Signalstörung hat IR 35 Verspätung und nähert sich "
                "gleichzeitig mit G 4 und IC 3 dem Kreuzungsabschnitt. "
                "Bitte entscheiden Sie, welchem Zug Vorfahrt gewährt werden soll."
            ),
            "options": [
                {
                    "label": "G 4 + IC 3 zuerst — IR 35 wartet 17 Schritte",
                    "kpis": {
                        "local_delay":  16,
                        "global_delay": 8,
                        "energy":       78,
                        "anschluss":    1,
                    },
                    "outcome": {
                        # IR35 wartet 15 Schritte ab Decision Step 22
                        "holds": {"Train_0": 15},
                    },
                },
                {
                    "label": "IR 35 zuerst — G 4 + IC 3 warten 12 Schritte",
                    "kpis": {
                        "local_delay":  24,
                        "global_delay": 14,
                        "energy":       72,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "holds": {
                            "Train_1": 12,
                            "Train_2": 12,
                        },
                    },
                },
                {
                    "label": "IR 35 wartet 12 Schritte — G 4 passiert, IC 3 wartet 20 Schritte",
                    "kpis": {
                        "local_delay":  18,
                        "global_delay": 10,
                        "energy":       75,
                        "anschluss":    1,
                    },
                    "outcome": {
                        "holds": {
                            "Train_0": 12,
                            "Train_2": 20,
                        },
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
            "Train_1": "G4 dann IC3",   # Option A: G4+IC3 first, IR35 waits 15
            "Train_2": "G4 dann IR35",  # Option C: IR35 waits 12, G4 passes, IC3 waits 20
        },
        "train_to_option": {
            "Train_0": 1,  # IR35 zuerst → Option B
            "Train_1": 0,  # G4 dann IC3 → Option A
            "Train_2": 2,  # G4 dann IR35 → Option C
        },
    },
}
