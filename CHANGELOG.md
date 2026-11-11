# Changelog


## Unreleased

### Added

- Railway: the Event and Context services accept the fields of the scripted Railway simulator (scenario, decision, run mode and session in events; session, scenario state, track network, history and decisions in contexts). All are optional, so existing Railway publishers keep working.
- Railway: the page is in German when the browser is set to German, including the platform texts it shows; English and French stay as before.
- Railway simulator: plays the six scripted scenarios on the platform. It sends its events and contexts through the Event and Context services, pauses at each decision until the operator's choice arrives, and is started, moved on and stopped through `/railway-simu/` (an Experiment of six runs, or a single run).
- Railway: "Get recommendation" on a decision card of the simulator shows the scenario's options with their KPIs, or the Ko-Lernen choices of train and action. Other Railway events still get the recommendation catalog.
- Railway: for the simulator's contexts the centre panel shows the "Kartenansicht": the scenario's track network, its stations and the trains with their direction, held trains in red. Contexts without a track network keep the geographic map.
- Railway: a "ZWL Diagramm" tab shows each train's distance along the scenario's line against the step, the planned paths dashed and the current step as a line.
- Railway: a "Linienansicht" tab shows the scenario's line straight, in three rows (the main line and the side tracks above and below it), with its stations and trains.
- Railway: a status line above the drawing shows the step and, while a decision is open, "Entscheidung erforderlich – bitte Ereigniskarte öffnen" with the held trains highlighted; a train table lists planned and actual departures and arrivals, delays and states.
- Railway: the operator applies a simulator recommendation from the assistant ("Lösung anwenden"); in Ko-Lernen they pick a train, then an action (actions not offered are greyed out, infeasible ones say why), and propose it. The choice goes to the simulator through the frontend's new `/railway-simu/` nginx proxy (`RAILWAY_SIMU_UPSTREAM`, default `http://host.docker.internal:5124/`), which resumes the run. Catalog recommendations are still applied through `/transport_plan`.
- Railway: when the simulator is reachable, a start dialog over the page starts the Experiment (six runs, each with its introduction and "Weiter") or a single run, and ends with "Experiment abgeschlossen" and a hint to log out; a bar above the timeline shows "Experiment i/6 · scenario — mode · Schritt N" and "✕ Beenden". Without the simulator the page stays as before.
- Survey: after logging out of Railway, the post-logout survey asks the experiment's reflection questions, in German (`CHAINS.Railway`).

## 1.5.2 (2026-11-05)

### Added

- PowerGrid survey in English or French: the operator picks the language before starting; the language is recorded with the answers. The English agreement score has the same changes as the French one (one statement at first, optional comment).
- PowerGrid simulator: 5 new scenarios for the small environment (January, March, July, September and November 2035).
- PowerGrid simulator: the scenario is chosen from a list in the dashboard.

### Fixed

- PowerGrid simulator: the time step duration accepts decimal values.

## 1.5.1 (2026-10-28)

### Fixed

- The recommendation service crashed at startup in the 1.5.0 image (`No module named 'psycopg'`): SQLAlchemy was not pinned and the build picked up 2.1, whose default PostgreSQL driver is not installed. Pinned to 2.0.54.

## 1.5.0 (2026-10-28)

### Added

- PowerGrid: several recommendation agents. At the start of a session the operator chooses Deep Expert, CurriculumAgent, the GNN agent or all of them. Recommendations do not name their agent (to avoid biasing the operator), but the session export records it.
- PowerGrid: uncertainty KPI in the recommendations table, for agents that estimate it (CurriculumAgent).
- PowerGrid: "Do nothing" option to resume the simulation without applying any recommendation.
- PowerGrid: post-logout survey replaced by the AI4REALNET power grid evaluation, in French (6 questionnaires: ATAI, agreement score, significance of human revisions, decision novelty, operator deskilling, long-term adoption).
- Session export: the agents chosen for the session, the agent of each recommendation, and "Do nothing" decisions (not counted as assistance).
- Cognitive state: Task Capacity read with the other factors. It is sent to the agents in `cognitive_snapshot` (`task_capacity`, `task_capacity_explainability`) and recorded in the session export.

### Fixed

- The side and bottom panels resize by dragging in every browser (Firefox included); a collapsed panel keeps its content, e.g. the recommendations shown.
- PowerGrid: asking for recommendations no longer fails with a network error when an agent is slow (the GNN agent, 15 s or more): no request waits for the agents any more, so nothing on the way can cut it.

### Changed

- Agents are configured with `RL_AGENT_<n>_API_URL`, `RL_AGENT_<n>_API_TOKEN` and `RL_AGENT_<n>_NAME` (agent 1 keeps `RL_AGENT_API_URL`); an agent without a URL is left out.
- Deep Expert proposes 3 recommendations when it is the session's only agent and 1 next to the others (`RL_AGENT[_<n>]_NUM_RECO` / `_NUM_RECO_SHARED`, sent as `num_reco`). Recommendations with the same title get a number.
- Each agent has its own response timeout, `RL_AGENT_<n>_TIMEOUT` (30 s by default, 60 s for the GNN agent); nginx allows 120 s on `/cab_recommendation/`.
- PowerGrid: each agent's recommendations are shown as soon as it answers, with the agents still working or that gave no answer. The frontend starts a job (`POST /cab_recommendation/api/v1/recommendation/jobs`) and polls it (`GET .../jobs/<id>`); jobs are kept in the recommendation database (new tables, created at startup) for an hour. `POST /recommendation` is unchanged.
- The agent call log gives each agent's response time.
- PowerGrid: the uncertainty row of the recommendations table now shows **Confidence** (100 % minus the agent's uncertainty, with its confidence level).
- PowerGrid: agents' French "Poursuivre" titles are shown as "Continue".
- PowerGrid: the unused "Use the study tool" button next to Apply is removed.
- While the session loads, "No context available" reads "Please wait a few seconds while the session is loading…" (and the same when asking for recommendations too early).
- Session export: times are in French local time with their offset (e.g. `2026-10-26T13:22:08.123+01:00`, +2 in summer) instead of UTC, in the JSON, the HTML report and the file name.
- PowerGrid: agents are no longer named to the operator, to avoid biasing them: no agent row in the recommendations table, no agent name in titles (a title proposed by two agents is numbered, "Continue (2)"), and neutral waiting messages ("Waiting for 2 more agents…"). The agent of each recommendation is still recorded in the session export.
- PowerGrid: the Confidence row is shown only when the session uses a single agent.
- PowerGrid: the unused "Use the analysis tool" button is removed.
- Survey: new version of the agreement score questionnaire (one statement at first, optional comment).

## 1.4.2 (2026-10-07)

### Added

- Decision time KPIs show **mean ± standard deviation** and the number of decisions they cover.
- ATM: aircraft heading, 5 NM protected zones that turn red on loss of separation, and airspace shapes (sectors, weather, volcanic ash, obstacles) on the map. The timeline follows the simulator clock.

### Fixed

- Decision times are measured per applied recommendation. The averages no longer count events without an action, and asking for recommendations again no longer adds the idle time before it.
- An event that comes back after being resolved is logged as a new occurrence.
- New events appear without reloading the page: the card stream reconnects when it drops, and
  cards split across network packets are no longer lost.
- The first context of a fresh deployment is displayed without logging out and back in.

### Changed

- Session log: the cognitive snapshot timestamp is stored once instead of once per factor.

## 1.4.1 (2026-09-17)

### Added

- HMI survey after logout, with a confirmation before skipping it. The session report is offered once the survey is done.
- Human decision time KPI (recommendations displayed → Apply) in the session report.
- On logout, choose whether to delete or keep the remaining alerts.
- Grid observation attached to each logged event, and a copy button for the session id.

### Fixed

- The HTML report download is no longer cancelled.

## 1.4.0 (2026-09-04)

Includes 1.3.8 and 1.3.9.

### Changed

- nginx is configured when the container starts, so proxy targets change without a rebuild.
- The cognitive API token is injected server-side by nginx: it is no longer in the JavaScript
  bundle, can be rotated without a rebuild, and the container fails to start without it.

### Fixed

- Applying a recommendation really sends it to the simulator, and failures are reported.

## 1.3.7 (2026-08-27)

### Fixed

- Session token refresh, and the PowerGrid apply proxy.

## 1.3.6 (2026-08-06)

### Changed

- PowerGrid simulator: improved interface, separate local and server deployments.
- PowerGrid: ontology recommendations removed.

## 1.3.4 (2026-07-29)

### Added

- Cognitive data is collected only with the operator's consent.
- PowerGrid: zoomable topology (SVG); Railway: KPI-based recommendation sorting.
- AI agent integration guide.

### Fixed

- PowerGrid: the applied action is sent to the simulator.

## 1.3.0 – 1.3.3 (2026-05-21 – 2026-05-22)

### Added

- Operator cognitive state from the INESC TEC API (via an nginx proxy), attached to the session
  traces.

### Changed

- The RL agent URL and token, and the cognitive API token, are read from environment variables.

### Fixed

- nginx proxy for the RL agent API, and connection errors reported.
- Event context images shown in the HTML report and left out of the JSON export.
- Deployment on OVH (1.3.1 – 1.3.3).

## 1.2.0 – 1.2.2 (2026-03-26)

### Added

- A card is marked resolved once its recommendation is applied.
- Session export: event titles, summaries and publish dates; large payloads are protected.

### Fixed

- nginx proxy buffering (1.2.1, 1.2.2).

> Applying recommendations and the session expiry were temporarily disabled in this version for demonstrations demo; they are back since 1.3.7 and 1.4.0.

## 1.1.0 (2026-03-25)

### Added

- Session traces: events, recommendation requests, feedback and applied solutions are recorded
  during the session, and exported on logout as JSON with per-event and session KPIs, plus an
  HTML summary.
- Recommendations view with a KPI comparison table.
- Docker images published to Docker Hub, compose files to run from them, and Kubernetes resources.

## 1.0.0 (2026-01-28)

First versioned release of InteractiveAI (formerly CAB).

### Added

- Three use cases: PowerGrid, Railway and ATM (multiple aircraft per context).
- Distinction between alerts and alarms in notifications.
- PowerGrid: grid state sent after a line disconnection in anticipation cards, and readable line
  names (`origin:extremity:line`).
- CI building the Docker images.

### Changed

- Everything in English; CAB renamed to InteractiveAI, RTE to PowerGrid.
- Scripts use Docker Compose V2; `checkPorts.sh` checks the required ports.

Before 1.0.0, the project was released as proofs of concept (`POC_V1` to `POC_V4.1`, 2022 – 2024).
