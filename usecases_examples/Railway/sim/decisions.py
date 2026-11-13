"""
Rules of the scripted decision points (pure functions, no Flatland).

- normalize_holds(): one reader for all hold formats used in the scenarios.
- colearning_view(): what Ko-Lernen offers (trains, actions, KPIs per train).
- match_colearning(): which scenario option a Ko-Lernen choice applies.

Moved out of app.py (/session/status and /session/colearning_action).

Bugfixes (06.11.2026):
- Option outcomes written as {"hold_trains": [...], "hold_steps": n} were
  ignored by ScenarioPlayer.apply_decision (only "holds" was read).
  Scenario 5 option 0 therefore held nobody and ended in a deadlock.
- Ko-Lernen showed the KPIs of one option and applied another (scenario 4:
  Train_1 / Train_2), because /session/status guessed the option while
  /session/colearning_action used train_to_option. Both now use
  match_colearning().
- "warten" ignored trains held via the "holds" dict.
"""

from typing import Dict, List, Optional, Tuple

ACTIONS = ("vorfahrt", "warten", "umleiten")


def normalize_holds(outcome: dict) -> Dict[str, int]:
    """{train_id: hold steps} from "holds", "hold_trains"+"hold_steps" or "hold_train"+"hold_steps"."""
    holds = {t: int(s) for t, s in outcome.get("holds", {}).items()}
    steps = int(outcome.get("hold_steps", 0))
    for t in outcome.get("hold_trains", []):
        holds.setdefault(t, steps)
    if outcome.get("hold_train"):
        holds.setdefault(outcome["hold_train"], steps)
    return {t: s for t, s in holds.items() if s > 0}


def held_trains(outcome: dict) -> set:
    return set(normalize_holds(outcome))


def match_colearning(scenario: dict, dp: dict, train: str, action: str) -> Tuple[Optional[int], str]:
    """
    Option index for a Ko-Lernen choice (train + action), or (None, reason).

    Order: invalid action -> not feasible; explicit train_to_option;
    otherwise the first option where the train is held (warten), not held
    (vorfahrt) or has scripted actions (umleiten).
    """
    cfg = scenario.get("colearning_config", {})
    options = dp.get("options", [])
    if action in cfg.get("invalid_actions", []):
        return None, "Diese Aktion ist für dieses Szenario nicht möglich."
    idx = cfg.get("train_to_option", {}).get(train)
    if idx is not None and 0 <= idx < len(options):
        return idx, ""
    for i, opt in enumerate(options):
        outcome = opt.get("outcome", {})
        held = held_trains(outcome)
        if action == "warten" and train in held:
            return i, ""
        if action == "vorfahrt" and train not in held:
            return i, ""
        if action == "umleiten" and train in outcome.get("scripted_actions", {}):
            return i, ""
    return None, f"Keine Lösung für '{action}' mit {train} verfügbar."


def colearning_view(scenario: dict, dp: dict) -> dict:
    """
    Ko-Lernen offer for a decision point:
    {"trains": [...], "train_actions": {train: [actions]}, "invalid_actions": [...],
     "train_labels": {...}, "kpis_by_train": {train: kpis of its "vorfahrt" option}}
    """
    cfg = scenario.get("colearning_config")
    options = dp.get("options", [])
    if cfg:
        trains = list(cfg.get("trains", []))
        train_actions = {t: list(cfg.get("actions", ["warten"])) for t in trains}
    else:
        # Same derivation as the old /session/status fallback:
        # held -> warten; only scripted -> umleiten; not held in an option with holds -> vorfahrt
        train_actions: Dict[str, List[str]] = {}
        everyone = set()
        for opt in options:
            o = opt.get("outcome", {})
            everyone |= held_trains(o) | set(o.get("scripted_actions", {}))
        for opt in options:
            for t in held_trains(opt.get("outcome", {})):
                train_actions.setdefault(t, []).append("warten")
        for opt in options:
            for t in opt.get("outcome", {}).get("scripted_actions", {}):
                if t not in train_actions:
                    train_actions[t] = ["umleiten"]
        for opt in options:
            held = held_trains(opt.get("outcome", {}))
            for t in (everyone - held if held else set()):
                acts = train_actions.setdefault(t, [])
                if "vorfahrt" not in acts:
                    acts.append("vorfahrt")
        train_actions = {t: list(dict.fromkeys(a)) for t, a in train_actions.items()}
        trains = sorted(train_actions)
        cfg = {}

    kpis_by_train = {}
    for t in trains:
        idx, _ = match_colearning(scenario, dp, t, "vorfahrt")
        if idx is not None:
            kpis_by_train[t] = options[idx].get("kpis", {})
    return {
        "trains": sorted(trains),
        "train_actions": train_actions,
        "invalid_actions": list(cfg.get("invalid_actions", [])),
        "train_labels": dict(cfg.get("train_labels", {})),
        "kpis_by_train": kpis_by_train,
    }
