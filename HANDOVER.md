# Railway Use Case — Deployment Handover

## What was built
A Flatland railway dispatcher training tool integrated into InteractiveAI (SystemX).
Two scenarios (Kreuzungskonflikt, Fahrt auf Sichtweite) with Recommendation and Co-Learning modes.

## New services (not in original docker-compose)

### 1. Flask Railway Brain (`railway-brain`)
- **Source:** `usecases_examples/Railway/`
- **Dockerfile:** `usecases_examples/Railway/Railway.Dockerfile`
- **Port:** 5001
- **Runs:** Flatland simulation + scenario player + card publishing

### 2. ZWL Angular Frontend (`zwl-frontend`)
- **Source:** `flatland-hmi-hack4rail/frontend/`
- **Dockerfile:** `flatland-hmi-hack4rail/zwl.Dockerfile`
- **Port:** 4200
- **Shows:** Kartenansicht (map) + ZWL Diagramm (Marey)

## To deploy on server

1. Copy `.env.example` → `.env` and fill in:
   ```
   VITE_RAILWAY_SIMU=http://<SERVER_PUBLIC_IP>:5001
   RL_AGENT_API_URL=http://railway-brain:5001/recommendations
   ```

2. Run:
   ```bash
   docker compose \
     -f config/dev/cab-standalone/docker-compose.yml \
     -f config/dev/cab-standalone/docker-compose-railway.yml \
     up --build
   ```

3. On first start, run the MongoDB perimeter init manually (timing issue with auto-init):
   ```bash
   docker exec cab-standalone-mongodb-1 mongo operator-fabric \
     -u root -p password --authenticationDatabase admin \
     /docker-entrypoint-initdb.d/01-cabprocess.js
   ```

## Decisions for SystemX developer

- **Port 5001 public access:** Flask brain must be reachable from the browser.
  Options: expose port directly, or proxy via nginx at `/railway-api/`.
  If proxied, update all `BACKEND_URL` in the Angular services + Vue frontend.

- **Authentication:** `AUTH_DISABLED=true` is set everywhere.
  Enable auth when deploying to production.

- **ZWL build output path:** Check `angular.json` `outputPath` — the Dockerfile
  assumes `dist/frontend/browser`. Adjust if different.

- **Maps volume:** `usecases_examples/Railway/maps/` contains JSON map files
  needed at runtime. Mount as volume or bake into Docker image.

## Files changed from original InteractiveAI repo
- `frontend/src/entities/Railway/CAB/` — all CAB Vue components
- `usecases_examples/Railway/app.py` — Flask brain (heavily extended)
- `usecases_examples/Railway/ScenarioPlayer.py` — new file
- `usecases_examples/Railway/FlatlandMapLoader.py` — new file
- `usecases_examples/Railway/ExperimentLogger.py` — new file
- `experiment_scenarios/` — new directory with scenario definitions
- `flatland-hmi-hack4rail/frontend/src/app/` — ZWL Angular components
