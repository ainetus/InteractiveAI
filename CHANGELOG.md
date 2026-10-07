# Changelog


## Unreleased

### Added

- PowerGrid: several recommendation agents. At the start of a session the operator chooses Deep Expert, CurriculumAgent, the GNN agent or all of them; each recommendation shows the agent that made it.
- PowerGrid: uncertainty KPI in the recommendations table, for agents that estimate it (CurriculumAgent).
- PowerGrid: "Do nothing" option to resume the simulation without applying any recommendation.
- Session export: the agents chosen for the session, the agent of each recommendation, and "Do nothing" decisions (not counted as assistance).

### Changed

- Agents are configured with `RL_AGENT_<n>_API_URL`, `RL_AGENT_<n>_API_TOKEN` and `RL_AGENT_<n>_NAME` (agent 1 keeps `RL_AGENT_API_URL`); an agent without a URL is left out.

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
