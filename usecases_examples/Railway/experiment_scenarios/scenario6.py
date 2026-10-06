"""
scenario6.py — Anschlusskonflikt

Karte: maps/map6.json (15x20)

Stationen:
    Station 1: (8,  1) — IC3 Start
    Station 2: (8, 17) — IC3 Ziel
    Station 3: (2, 11) — S12 + IR35 Start (Northbound)
    Station 4: (13,11) — S12 + IR35 Ziel (Southbound)

Züge:
    Train0 = IC3:  Station1 → Station2  dir=1 (Ost)  dep=1
    Train1 = S12:  Station3 → Station4  dir=2 (Süd)  dep=1
    Train2 = IR35: Station3 → Station4  dir=2 (Süd)  dep=10
"""

SCENARIO_6 = {
    "id":   "scenario6",
    "name": "Szenario 6 — Anschlusskonflikt",
    "map":  "maps/map6.json",
    "marey_link": {"start": [8, 1], "end": [8, 17]},

    "agent_defs": [
        dict(start=(8,  1), target=(8, 17), dir=1, dep=1,  arr=20, name="IC 3"),
        dict(start=(2, 11), target=(13,11), dir=2, dep=9,  arr=23, name="S 12"),
        dict(start=(2, 11), target=(13,11), dir=2, dep=18, arr=32, name="IR 35"),
    ],

    "events": [
        {
            "timestep":         5,
            "type":             "train_delay",
            "train":            "Train_0",
            "duration":         8,
            "push_card":        True,
            "card_title":       "Betriebsstörung — IC 3",
            "card_description": (
                "IC 3 meldet eine technische Störung an der Zugtüre. "
                "Der Zug muss an der aktuellen Position anhalten und auf Freigabe warten. "
                "Geschätzte Wartezeit: 8 Zeitschritte."
            ),
        },
        {
            "timestep":         13,
            "type":             "info",
            "train":            "Train_0",
            "duration":         0,
            "push_card":        True,
            "card_title":       "Anschlusskonflikt — IC 3 verspätet",
            "card_description": (
                "Durch die Verspätung von IC 3 gerät der geplante Anschluss mit S 12 "
                "in Gefahr. Bitte entscheiden Sie, ob S 12 auf IC 3 warten soll."
            ),
        },
    ],

    "decision_points": [
        {
            "timestep":    13,
            "description": (
                "IC 3 hat durch die Betriebsstörung 8 Zeitschritte Verspätung. "
                "S 12 nähert sich dem Kreuzungspunkt. "
                "Soll S 12 auf IC 3 warten oder normal weiterfahren?"
            ),
            "options": [
                {
                    "label": "S 12 passieren lassen — Passagiere über Anschlussverlust informieren, Späterer Anschluss: IR 35",
                    "kpis": {
                        "local_delay":  0,
                        "global_delay": 8,
                        "energy":       90,
                        "anschluss":    0,
                    },
                    "outcome": {},
                },
                {
                    "label": "S 12 wartet 7 Schritte — Anschluss für IC 3 sichern",
                    "kpis": {
                        "local_delay":  7,
                        "global_delay": 4,
                        "energy":       82,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "holds": {"Train_1": 7},
                    },
                },
            ],
        },
    ],

    "colearning_config": {
        "trains":          ["Train_1", "Train_0"],
        "actions":         ["vorfahrt"],
        "invalid_actions": [],
        "train_to_option": {
            "Train_1": 0,  # Vorfahrt S12 → Option A (weiterfahren)
            "Train_0": 1,  # Vorfahrt IC3 → Option B (S12 wartet 7 Schritte)
        },
    },
}
