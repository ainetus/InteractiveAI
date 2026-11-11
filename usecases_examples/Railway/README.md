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
  - [1.6 On the platform: session runner and HTTP app](#16-on-the-platform-session-runner-and-http-app)
- [2 Dev stack without Docker](#2-dev-stack-without-docker)
  - [2.1 Start](#21-start)
  - [2.2 Check](#22-check)
  - [2.3 Screenshots and video](#23-screenshots-and-video)

## 1 Simulator

The player is headless: no network, no rendering. On the platform, a session runner steps it and an
HTTP app receives the session controls and the operator's choice (§1.6). Nothing is computed live: events, decision options,
their KPIs and outcomes are written into the scenario files.

### 1.1 Requirements

Python 3.10 or later, `flatland-rl==4.2.6` (the step rules in `sim/` were measured on it),
`numpy<2`, and Flask and requests for the platform integration. From this folder:

```sh
python -m pip install -r requirements.txt
```

### 1.2 Run a scenario in the terminal

The settings (one scenario and its mode, or the Experiment seeded by a session id; the choice made
at the decision point; what to print) are in `config.py`:

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
(`EXPECTED_ARRIVALS`), the Ko-Lernen mapping and the payloads. `tests/test_integration.py` checks the
publisher (one token, request paths), the run list, the session runner (contexts on change, the
pause at the decision, apply, next, stop, the request budget per scenario) and the HTTP routes,
without a platform (`requests_mock`, Flask's test client).

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
| `integration/session.py` | the session and its run list: the Experiment or a single run, seeded by the session id |
| `integration/publisher.py` | `Publisher`: sends events and contexts to the platform with one reused token |
| `integration/loop.py` | `SessionRunner`: plays the run list at the configured pace, sends what the hooks report |
| `app.py` | the HTTP app: scenario list, session start / next / stop, the applied choice |
| `export_recommendations.py`, `recommendations.json` | every decision's recommendations per mode, generated from the scenario files; copied to the Recommendation Service |
| `experiment_scenarios/` | the six scenarios (German texts, with their introductions) |
| `maps/` | `map1`–`map6`, drawn maps |
| `run_scenario.py`, `config.py` | terminal demo |
| `tests/` | pytest: `test_sim.py`, `test_integration.py`, `test_recommendations.py` |

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

### 1.6 On the platform: session runner and HTTP app

`python app.py` starts the simulator as a service (port 5124), idle until the page starts a
session. The browser reaches it only through the frontend nginx's `/railway-simu/`; it sends events
and contexts to the platform's `/cab_event/` and `/cabcontext/` as `publisher_test`.

| Route | Does |
|---|---|
| `GET /api/v1/scenarios` | id, name and introduction of every scenario |
| `POST /api/v1/session` | starts a session: `{"session_id", "kind": "experiment"}` (six runs, three per mode, seeded by the session id) or `{"session_id", "kind": "single", "scenario_id", "mode"}`; posts run 1 as `ready`; ends a running session of another `session_id` first; 409 for the same one |
| `POST /api/v1/session/next` | starts run 1, or the next run after a complete one |
| `POST /api/v1/session/stop` | ends the session ("✕ Beenden") |
| `POST /api/v1/recommendations` | the applied choice, `actions[0]` of the recommendation plus the card's `event_id`; 409 when it is not the open decision |
| `GET /health` | `{"status": "ok"}` |

- **Pace:** `RAILWAY_STEPS_PER_SECOND` (default 1). The participant does not control time: a run
  pauses itself at its decision point, and only the applied choice resumes it.
- **Requests:** contexts on change only: at the session start, at every event, at the decision, after
  it, at the end of a run and every N steps while trains move (N steps ≈ the page's 5 s poll); none
  while paused or between runs. About 10–20 contexts and 1–3 events per scenario.
- **Platform:** `RAILWAY_PLATFORM_URL` (the platform's URL; default the dev gateway
  `http://127.0.0.1:3200`), `RAILWAY_PUBLISHER_USER`, `RAILWAY_PUBLISHER_PASSWORD` (default
  `publisher_test` / `test`). `RAILWAY_SIMU_HOST`, `RAILWAY_SIMU_PORT` (default `0.0.0.0`, 5124).
- **One session at a time** per simulator process, so one participant at a time.
- **Recommendations:** the simulator does not answer recommendation requests. The Recommendation
  Service's `RailwayManager` answers them from its copy of `recommendations.json`, looked up by the
  card's `scenario_id`, `decision_index` and `run_mode`; other Railway events get its catalog as
  before. After changing a scenario, regenerate both files:

  ```sh
  python export_recommendations.py
  ```

  `tests/test_recommendations.py` fails while either file differs from the script's output. The
  Recommendation Service's image has to be rebuilt for a new copy.
- **Introductions:** scenario 3's is `railway_sim`'s text; those of scenarios 1, 2, 4, 5 and 6 are
  drafts written from the scenarios' situations, to be replaced by `railway_sim`'s texts.

## 2 Dev stack without Docker

The platform on one machine, for development and screenshots: the real Event (5000), Context (5100),
Historic (5200) and Recommendation (5400) services on SQLite with `AUTH_DISABLED=true`, registered for
Railway, and the Railway simulator (5124, §1.6), behind a small gateway on port 3200
(`devstack/gateway.py`). The gateway routes to the
services as the frontend nginx does and stands in for Keycloak (any login is accepted) and
OperatorFabric (cards kept in memory, the card stream). Never expose it beyond localhost.

### 2.1 Start

Requirements: Python 3.11 (the services' version) and, for the frontend, Node 20 with its npm, as
pinned in `frontend/.nvmrc` (`nvm use` in `frontend/`). Install the frontend's packages once, as its
`Dockerfile` does, and build it with the simulator's proxy path:

```sh
cd frontend && npm ci && VITE_RAILWAY_SIMU=/railway-simu npm run build-only
```

Then, from the repository root:

```sh
usecases_examples/Railway/devstack/start.sh
```

With the Vite dev server and hot reload instead of the built bundle (after `npm ci`, no build), and
the simulator at 4 steps per second:

```sh
RAILWAY_STEPS_PER_SECOND=4 FRONTEND=vite usecases_examples/Railway/devstack/start.sh
```

- The first start creates a venv from Python 3.11 or 3.12 (`python3.11`, `python3.12` or `python3`
  on `PATH`, or `DEVSTACK_BASE_PYTHON`) and installs `devstack/requirements.txt` (the services'
  Railway path, without PowerGrid's `torch`). Python 3.13 and later don't work: the services' pinned
  SQLAlchemy 2.0.16 fails there. `DEVSTACK_PYTHON` uses an interpreter with the requirements
  installed instead.
- A second venv, made the same way, holds the simulator's `requirements.txt` (Flatland);
  `RAILWAY_SIM_PYTHON` uses an interpreter with them installed instead.
- The venv, the SQLite files and the logs go to `.cache/railway-devstack/` in the repository root
  (gitignored; `DEVSTACK_HOME` moves them). Delete `data/` there to start from an empty database.
- `FRONTEND_DIST` serves another built bundle, `FRONTEND_DIR` runs Vite in another checkout of the
  frontend, `GATEWAY_PORT` changes the port. Ctrl-C stops everything.

Open http://localhost:3200 and log in with any user and password (e.g. `railway_user` / `test`).

### 2.2 Check

```sh
python usecases_examples/Railway/devstack/smoke.py
```

posts one event and one context through the gateway and reads them back (exit code 0 when all
pass). `devstack/seed.py` posts one Railway event and context in the current schema, for the page
to show something.

### 2.3 Screenshots and video

With the dev stack running and seeded, from `frontend/`:

```sh
CYPRESS_BASE_URL=http://localhost:3200 npx cypress run --spec cypress/e2e/railway.cy.ts
```

The shots go to `frontend/cypress/screenshots/railway.cy.ts/` (1600×900), the video to
`frontend/cypress/videos/`; both are gitignored. Against another deployment, set `CYPRESS_BASE_URL`
and a participant login (`CYPRESS_USER`, `CYPRESS_PASSWORD`).
