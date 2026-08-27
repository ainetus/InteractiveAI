"""
scenario1.py — Szenario 1: Kreuzungskonflikt Einspurabschnitt

Ablauf:
  Schritte 1-5:   Normaler Betrieb. IC 301 Richtung Süden, S 420 + S 425 Richtung Norden.
  Schritt 5:      Türstörung IC 301 → Zug bleibt stehen (12 Schritte).
  Schritt 20:     Warnung: Kreuzungskonflikt im Einspurabschnitt.
  Schritt 22:     Entscheidungspunkt: Wer kreuzt zuerst?

Karte:    maps/drawn_environment_export.json (15×20, Zweibahnhof-Korridor)
Züge:
    IC 301 (Agent 0): Stadtbahnhof (oben) → Südbahnhof (unten)
    S 420  (Agent 1): Südbahnhof → Stadtbahnhof, Abfahrt +7 Schritte später
    S 425  (Agent 2): Südbahnhof → Stadtbahnhof, Abfahrt +10 Schritte später
"""

SCENARIO_1 = {
    "id":   "scenario1",
    "name": "Szenario 1 — Kreuzungskonflikt",
    "map":  "maps/drawn_environment_export.json",

    # direction=3: Einstieg von Westen (Flatland 4.x Konvention für Ostfahrt)
    "agent_defs": [
        dict(start=(0,  5), target=(14, 8), dir=3, dep=1,  arr=90,  name="IC 301"),
        dict(start=(14, 5), target=(0,  8), dir=3, dep=10, arr=90,  name="S 420"),
        dict(start=(13, 5), target=(0,  8), dir=3, dep=13, arr=95,  name="S 425"),
    ],

    # Co-learning: only IC 301 (Train_0) and S 420 (Train_1) selectable
    # S 425 follows automatically — dispatcher doesn't need to select it
    "colearning_config": {
        "trains":  ["Train_0", "Train_1"],
        "actions":         ["warten", "umleiten"],
        "invalid_actions": ["umleiten"],
    },

    "events": [
        {
            "timestep":         15,
            "type":             "train_delay",
            "train":            "Train_0",
            "duration":         8,
            "card_title":       "Türstörung — IC 301",
            "card_description": (
                "An IC 301 wurde eine Türstörung gemeldet. "
                "Der Zug muss an der aktuellen Position anhalten. "
                "Geschätzte Verzögerung: 8 Zeitschritte."
            ),
        },
        {
            "timestep":         23,
            "type":             "info",
            "train":            "Train_0",
            "duration":         0,
            "push_card":        True,
            "card_title":       "Kreuzungskonflikt — Dispositionsentscheid erforderlich",
            "card_description": (
                "Infolge der Türstörung hat IC 301 Verspätung und trifft nun gleichzeitig "
                "mit S 420 und S 425 am Einspurabschnitt ein. "
                "Eine planmässige Kreuzung ist nicht mehr möglich. "
                "Es ist zu entscheiden, welcher Zug den Abschnitt zuerst passiert."
            ),
        },
    ],
    "decision_points": [
        {
            "timestep":    23,
            "description": (
                "IC 301 und S 420 / S 425 nähern sich gleichzeitig dem Einspurabschnitt. "
                "Durch die Türstörung ist die ursprünglich geplante Kreuzung nicht mehr möglich. "
                "Bitte entscheiden, welcher Zug den Abschnitt zuerst passiert."
            ),
            "options": [
                {
                    "label": "IC 301 wartet — S 420 und S 425 passieren zuerst",
                    "kpis": {
                        "local_delay":  18,  # IC301 ~18 min verspätet
                        "global_delay": 22,
                        "energy":       74,
                        "anschluss":    2,
                    },
                    "outcome": {
                        "hold_train":  "Train_0",
                        "hold_steps":  15,             # released at step 38 (23+15)
                        # S trains take the bypass (right turn at junction)
                        "scripted_actions": {
                            "Train_1": [2]*9  + [3] + [2]*50,  # right at step 32
                            "Train_2": [2]*10 + [3, 3, 3, 3] + [2]*50,  # try right steps 33-36
                        },
                    }
                },
                {
                    "label": "S 420 und S 425 warten — IC 301 passiert zuerst",
                    "kpis": {
                        "local_delay":  32,  # S420+S425 je ~16 min
                        "global_delay": 18,
                        "energy":       69,
                        "anschluss":    3,
                    },
                    "outcome": {
                        "hold_trains": ["Train_1", "Train_2"],
                        "hold_steps":  9,           # released at step 32 (23+9)
                        # IC301 tries LEFT at junction steps 30-33 (indices 7-10)
                        # Flatland uses FORWARD if LEFT is not valid at that cell
                        "scripted_actions": {
                            "Train_0": [2]*7 + [1, 1, 1, 1] + [2]*50,
                        },
                    }
                },
            ],
        }
    ],
}
