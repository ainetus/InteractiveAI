# Changelog

Bug fixes and infrastructure/feature changes made to this repo, in the order
they were done. Each entry says what was broken, how it was found/verified,
and what changed.

---

## 1. Added `setup.sh` / `stop.sh`

One-shot scripts to bring the local stack up and down: start the
`cab-standalone` backend, wait for Keycloak and configure it via the admin
REST API, rebuild `frontend`/`cabrecommendation` from source, load
OperatorFabric resources and register use cases, and build/start the
PowerGrid simulator. `stop.sh` supports `--pause` (stop, keep containers),
default (remove containers, keep data volumes), and `--wipe` (remove
volumes too). Verified with a full live `docker compose` bring-up and both
teardown modes.

## 2. Port conflict: `cabcontext` vs. PowerGrid simulator (both `5100`)

`config/dev/cab-standalone/docker-compose.yml` published `cabcontext` on host
port `5100`, colliding with the PowerGrid simulator app (also `5100`).
Remapped `cabcontext` to `5101:5000`.

## 3. Hardcoded personal LAN IP in the PowerGrid simulator proxy

`nginx-cors-permissive.conf`'s `/powergrid-simu/` location proxied to
`http://192.168.208.61:5100/` — a machine-specific address that only worked
on the machine it was written on. Replaced with `http://host.docker.internal:5100/`,
and added `extra_hosts: ["host.docker.internal:host-gateway"]` to the
`frontend` service (cab-standalone) and to the PowerGrid simulator's `app`
service, so the mapping resolves on any machine. Also added
`cab_server_url_0 = "http://host.docker.internal:3200/"` to
`API_POWERGRID_CAB.toml` for a working local-dev server option in the
simulator's login page.

## 4. Entity assignment to `publisher_test` missing from `resources/loadTestConf.sh`

Without it, `publisher_test` had no entities assigned and the Home page
showed no entity cards, making PowerGrid/ATM/Railway unreachable. Added a
`PUT /users/users/publisher_test` call (assigning `PowerGrid`, `ATM`,
`Railway`) after use cases are registered.

## 5. `usecases_examples/PowerGrid/Dockerfile.app` was cache-unfriendly and bloated

Code was copied before `requirements-app.txt` (busts the dependency layer
cache on every source edit), the apt install used no
`--no-install-recommends` and didn't clean `/var/lib/apt/lists`, and a stray
`EXPOSE 5000` remained despite port publishing being handled by compose.
Reordered (deps before source) and cleaned up.

## 6. PowerGrid recommendation-service could not import

`backend/recommendation-service/resources/PowerGrid/manager.py` imported
`AgentType` from a `PowerGridgrid2op_poc_simulator` package that doesn't
exist in this repo. Every PowerGrid use-case registration
(`POST /api/v1/usecases`) raised `ModuleNotFoundError` — the ontology
recommendation pipeline for PowerGrid was dead on arrival. Fixed by inlining
the small `AgentType` enum directly in `manager.py`. Verified live: use-case
registration, `POST /api/v1/recommendation`, and the smoke test (below) all
pass.

## 7. Broken/incomplete test infrastructure in `backend/recommendation-service`

- `tests/test_views.py::test_PowerGrid_get_recommendation` opened
  `tests/tests_resources/PowerGrid_recommendation.json`, which doesn't exist —
  only `rte_recommendation.json` (same shape/content) is present. Fixed the
  filename.
- `pytest-mock` was missing from `requirements.txt` despite `conftest.py`'s
  `PowerGrid_auth_mocker` fixture already depending on the `mocker` fixture —
  the existing test suite could not have run as committed. Added
  `pytest-mock==3.14.0`.
- Added `test_smoke_pipeline.py`: an end-to-end smoke test of the PowerGrid
  recommendation pipeline. It stubs out the external RL call (no local agent
  to exercise by default) and asserts the ontology-recommendation path
  returns a well-formed recommendation through the real Flask view/auth
  stack. All 3 tests in the service pass (verified inside the actual
  `cab_recommendation` container, which has the full dependency stack —
  running `pytest` bare on a host machine without `cab_common` installed and
  the right `PYTHONPATH`/cwd will not work).

## 8. Frontend: auto-logout on a dead session token was disabled ("TEMP HACK (eval-demo)")

Reported symptom: repeated `Unauthorized` on `/cabcontext/api/v1/contexts`
with no recovery. Root cause: `frontend/src/plugins/http.ts` had the recovery
block (call `authStore.checkToken()` on a failed request, log out and
redirect to `/login` if the token is truly dead) fully commented out, marked
`TODO: TEMP HACK (eval-demo) — MUST BE REMOVED before next release`. Once a
token stopped being valid (e.g. idle session timeout), the frontend had no
recovery path and kept resending the same dead token forever. Re-enabled the
block. Rebuilt and confirmed the bundle no longer contains the hack.

## 9. Frontend: `getRecommendation` silently dropped the `use_case` query parameter

Reported symptom: clicking "fetch recommendations" failed with `400 Bad
Request`. Root cause: `frontend/src/api/services.ts`'s `getRecommendation`
didn't accept or send a `use_case` parameter at all, but the
recommendation-service requires one when a token is registered for more than
one entity (e.g. `publisher_test` with `Railway;ATM;PowerGrid`). Fixed by
adding `use_case` as an optional query param on `getRecommendation` in
`api/services.ts`, passed from `stores/services.ts` as
`event.entityRecipients[0]`. Reproduced the exact 400 with a real
multi-entity token and confirmed the fix resolves it (200 with a real
ontology recommendation).

## 10. Frontend: `applyRecommendation` was faking success for ATM/Railway/PowerGrid ("TEMP HACK (eval-demo)")

Three separate copies of the same disabled-with-fake-success pattern:

- `frontend/src/api/services.ts` — dead code, not imported/used anywhere
  (each entity has its own `applyRecommendation` in `entities/<Entity>/api.ts`).
  Restored the real `http.post('/api/v1/recommendations', data)` call anyway,
  for consistency.
- `frontend/src/entities/ATM/api.ts` and `frontend/src/entities/Railway/api.ts`
  — these ARE live/used by the UI. Restored their real simulator calls
  (`VITE_ATM_SIMU + '/update-flight-plan'`, `VITE_RAILWAY_SIMU + '/transport_plan'`).
  Note: this repo has no ATM or Railway simulator (only
  `usecases_examples/PowerGrid` exists, and `VITE_ATM_SIMU`/`VITE_RAILWAY_SIMU`
  default to `"false"`), so applying a recommendation for those two entities
  will now fail with a real network error instead of silently pretending to
  succeed — expected until those simulators exist or are pointed at a real
  endpoint.

PowerGrid's own `applyRecommendation` (`entities/PowerGrid/api.ts`) was
already live and was not touched.

## 11. PowerGrid simulator login page was in French

`usecases_examples/PowerGrid/app/templates/index.html` had `lang="fr"` and
all UI text (labels, buttons, alerts) in French, while the rest of the app
(flash messages) is in English. Translated the page to English (`lang="en"`,
"Login", "Select a server", "Username", "Password", error alerts, etc).
Verified live at `http://localhost:5100/`.

## 12. Documented how to connect a local RL agent

Added a README section describing how to clone, build, and run the
`T2.1_deep_expert` RL agent service locally, and how to wire it into
`cabrecommendation` (`extra_hosts` + `RL_AGENT_API_URL` in `.secrets`) or
revert back to the default external agent URL. Verified end-to-end with a
live local agent: a PowerGrid recommendation request returned both a real
RL-agent recommendation and the ontology recommendation together. The
default state of this repo is disconnected (external agent URL, no local
`extra_hosts`/`.secrets` override).

**Known follow-up, not yet fixed:** the RL agent returns `agent_type` as a
raw enum int (`2`) rather than the string `"IA"` that the ontology path uses
and that the frontend (`Recommendations.vue`/`Assistant.vue`) checks
against — a recommendation from that agent may not render/behave correctly
in the UI as a result.

## Not investigated / out of scope so far

- The PowerGrid simulator's "line lost" event branch does not call the CAB
  recommendation API the way the "overload anticipation" branch does (only
  pauses for manual continuation).
- The `agent_type` int-vs-string mismatch noted in item 12.
