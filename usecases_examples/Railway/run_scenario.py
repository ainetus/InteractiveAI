"""
Play scripted scenarios headless in the terminal. Settings: config.py.

This is the stand-in for the InteractiveAI loop: where it prints, the real
simulator sends the event / context, and where it picks config.OPTION_INDEX
the real simulator waits for the operator's choice.
"""

import json

import config
from experiment_scenarios import ALL_SCENARIOS
from integration import payloads
from integration.session import current_run, experiment_runs, make_session, single_run
from sim.decisions import match_colearning
from sim.scenario_player import COMPLETE, PAUSED, Hooks, ScenarioPlayer

MAX_STEPS = 2000   # safety stop for this script


def _show(label, payload):
    if not config.PRINT_PAYLOADS or payload is None:
        return
    if label == "context":   # grid and history are long: show sizes only
        data = dict(payload["data"])
        data["infra"] = f"<{len(json.dumps(data['infra']))} bytes>"
        data["history"] = f"<{len(data['history'])} frames>"
        payload = {**payload, "data": data}
    print(f"--- {label} ---\n{json.dumps(payload, ensure_ascii=False, indent=1)}")


def play(scenario_id: str, session: dict):
    sc = ALL_SCENARIOS[scenario_id]
    mode = current_run(session)["mode"]
    infra = None

    def on_event(p, event):
        print(f"[{p.step_index:3d}] EVENT  {event.get('card_title', event.get('type'))}")
        _show("event", payloads.event_payload(p, event, session))

    def on_decision(p, dp):
        print(f"[{p.step_index:3d}] DECISION  {dp['description'][:80]}...")
        _show("decision event", payloads.decision_event(p, p.decision_index - 1, session))
        nonlocal infra
        if infra is None:
            infra = payloads.infra_payload(sc, p.timetable)
        _show("context", payloads.context_payload(p, session, infra))
        _show("recommendations", payloads.recommendations(sc, p.decision_index - 1,
                                                          mode, p.train_names))

    hooks = Hooks(on_event=on_event, on_decision=on_decision)
    player = ScenarioPlayer(sc, hooks)
    print(f"\n=== {sc['name']} ({mode}) ===")

    for _ in range(MAX_STEPS):
        if player.state == COMPLETE:
            break
        if player.state == PAUSED:
            dp = player.active_decision
            if mode == "colearning":
                idx, reason = match_colearning(sc, dp, config.COLEARNING_TRAIN, config.COLEARNING_ACTION)
                if idx is None:
                    print(f"      Ko-Lernen choice not feasible ({reason}) -> option 0")
                    idx = 0
                player.apply_decision(idx, source="colearning",
                                      meta={"train": config.COLEARNING_TRAIN, "action": config.COLEARNING_ACTION})
            else:
                player.apply_decision(config.OPTION_INDEX)
            print(f"      applied: {player.decisions[-1]['option_label']}")
            continue
        player.step()
        if config.PRINT_DISPATCH_EVENTS:
            for e in player.dispatcher.get_step_events():
                print("      ", e)

    print(f"Finished at step {player.step_index} ({player.state})")
    print(player.timetable.summary())
    return player


if __name__ == "__main__":
    runs = single_run(config.SCENARIO_ID, config.MODE) if config.SCENARIO_ID \
        else experiment_runs(config.SESSION_ID, list(ALL_SCENARIOS))
    session = make_session(config.SESSION_ID, runs)
    for pos, run in enumerate(session["scenario_order"]):
        session["scenario_position"] = pos
        play(run["scenario_id"], session)
