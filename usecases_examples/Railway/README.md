# Railway use case: scripted Flatland simulator

The simulator of the Railway dispatcher experiment: six scripted Flatland scenarios, two decision
modes ("Empfehlungsmodus", "Ko-Lernen"). It plays a scenario step by step and builds the events and
contexts the InteractiveAI platform shows. Design and plan:
[`docs/plans/railway-use-case.md`](../../docs/plans/railway-use-case.md).

- [1 Simulator](#1-simulator)
  - [1.1 Requirements](#11-requirements)
  - [1.2 Run a scenario in the terminal](#12-run-a-scenario-in-the-terminal)
  - [1.3 Tests](#13-tests)
  - [1.4 Project structure](#14-project-structure)
  - [1.5 How a scenario works](#15-how-a-scenario-works)

## 1 Simulator

Headless: no server, no network, no rendering. Nothing is computed live: events, decision options,
their KPIs and outcomes are written into the scenario files.

### 1.1 Requirements

Python 3.10 or later, `flatland-rl==4.2.6` (the step rules in `sim/` were measured on it),
`numpy<2`. From this folder:

```sh
python -m pip install -r requirements.txt
```

### 1.2 Run a scenario in the terminal

The settings (scenario, participant, mode, the choice made at the decision point, what to print) are
in `config.py`:

```sh
python run_scenario.py
```

With `PRINT_PAYLOADS = True` it prints the events, contexts and recommendations the platform would
receive.

### 1.3 Tests

```sh
python -m pytest -q
```

`tests/test_sim.py` checks the arrival steps of every scenario and option against a recorded run
(`EXPECTED_ARRIVALS`), the Ko-Lernen mapping and the payloads.

### 1.4 Project structure

| Path | Content |
|---|---|
| `sim/scenario_player.py` | `ScenarioPlayer`: plays one scenario step by step; `Hooks` for the integration |
| `sim/dispatcher.py` | moves the trains along their routes in Flatland |
| `sim/timetable.py` | planned and actual times per train |
| `sim/map_loader.py` | `maps/mapN.json` → Flatland env, shortest routes |
| `sim/decisions.py` | decision rules: holds, Ko-Lernen matching (`match_colearning()`, `colearning_view()`) |
| `sim/marey.py` | the line's ZWL distances, the planned paths and the link map (static per scenario) |
| `integration/payloads.py` | builds the context, event and recommendation JSON (no HTTP) |
| `integration/session.py` | participant, mode, scenario order (`make_session()`) |
| `experiment_scenarios/` | the six scenarios (German texts) |
| `maps/` | `map1`–`map6`, drawn maps |
| `run_scenario.py`, `config.py` | terminal demo |
| `tests/test_sim.py` | pytest |

The player has no thread and no timer; the caller sets the pace:

```python
from sim.scenario_player import ScenarioPlayer, Hooks, PAUSED, COMPLETE
p = ScenarioPlayer(scenario, Hooks(on_event=..., on_decision=..., on_step=..., on_resume=..., on_complete=...))
p.step()                      # one simulation step; does nothing while PAUSED / COMPLETE
p.apply_decision(i, source="recommendation" | "colearning", meta={...})
```

### 1.5 How a scenario works

- A scenario file defines a map, 2–3 trains (`agent_defs`), timed `events` and one decision point.
- A `train_delay` event holds a train for `duration` steps; an `info` event only shows a card.
- At the decision point the player pauses until an option is applied. Each option has fixed KPIs
  and a scripted outcome: holds per train and/or scripted Flatland actions.
- Empfehlungsmodus (`recommendation`): the operator picks one of the options. Ko-Lernen
  (`colearning`): the operator picks a train and an action (`vorfahrt`, `warten`, `umleiten`);
  `match_colearning()` maps it to an option, and actions in `invalid_actions` are offered but not
  feasible.

