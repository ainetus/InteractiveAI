# InteractiveAI Assistant Platform
**An interactive AI Assistant Platform for Real Time operations**

_Frontend_ 
[![Node](https://img.shields.io/badge/Node-339933?style=plastic&logo=nodedotjs&logoColor=fff)](https://nodejs.org) [![Vue](https://img.shields.io/badge/Vue-35495E?style=plastic&logo=vuedotjs&logoColor=fff)](https://vuejs.org) [![Vite](https://img.shields.io/badge/Vite-%23646CFF.svg?style=plastic&logo=vite&logoColor=fff)](https://vitejs.dev) [![TypeScript](https://img.shields.io/badge/Typescript-%23007ACC.svg?style=plastic&logo=typescript&logoColor=fff)](https://www.typescriptlang.org)

_Backend_ 
![Python](https://img.shields.io/badge/python-3670A0?style=plastic&logo=python&logoColor=ffdd54)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=plastic&logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=plastic&logo=docker&logoColor=white)

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#local-setup-step-by-step">Local Setup</a></li>
    <li><a href="#railway-use-case">Railway Use Case</a></li>
    <li><a href="#server-deployment">Server Deployment</a></li>
    <li><a href="#authentication">Authentication</a></li>
    <li><a href="#troubleshooting">Troubleshooting</a></li>
  </ol>
</details>

---

## About The Project

InteractiveAI is a prototype bi-directional virtual assistant platform for augmented decision-making in complex industrial operations. It is generic and supports multiple use cases including **PowerGrid**, **ATM**, and **Railway** (FHNW/AI4REALNET).

The platform uses **OperatorFabric** for notification management.

> **Railway use case:** Branch `FHNWtec-version` — https://github.com/ainetus/InteractiveAI/tree/FHNWtec-version

---

## Local Setup — Step by Step

### Prerequisites

- [Git](https://git-scm.com/)
- [Docker Engine 27+](https://www.docker.com/) with Docker Compose V2
- **Railway only:** Python 3.10, Node.js 18+

### 1. Clone the repository

```bash
git clone https://github.com/ainetus/InteractiveAI.git
cd InteractiveAI
git checkout FHNWtec-version
```

### 2. Set environment variables

```bash
export MSYS_NO_PATHCONV=1          # Windows Git Bash only
export USER_ID=1000
export USER_GID=1000
export SPRING_PROFILES_ACTIVE=docker
export CONFIG_PATH=./config/dev/cab-standalone
export VITE_RAILWAY_SIMU=http://localhost:5001
export RL_AGENT_API_URL=http://localhost:5001/recommendations
```

### 3. Start the main Docker stack

```bash
docker compose -f config/dev/cab-standalone/docker-compose.yml up -d
```

Open http://localhost:3200/cab/Railway in your browser to verify it's running.

### 4. Configure the database

Run once after each Docker start:

```bash
docker exec cab-standalone-mongodb-1 mongo operator-fabric \
  -u root -p password --authenticationDatabase admin \
  --eval 'db.perimeter.updateOne({_id:"cabProcess"},{$set:{process:"cabProcess",stateRights:[{state:"messageState",right:"ReceiveAndWrite"}]}},{upsert:true}); db.group.updateOne({_id:"Planner"},{$addToSet:{perimeters:"cabProcess"}}); db.group.updateOne({_id:"Dispatcher"},{$addToSet:{perimeters:"cabProcess"}}); print("done")'
```

Expected output:
```
MongoDB shell version v4.4.4
connecting to: mongodb://127.0.0.1:27017/operator-fabric?...
done
```

### 5. Install Python dependencies (first time only)

```bash
cd usecases_examples/Railway
python3.10 -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
cd ../..
```

### 6. Start Flask Railway brain *(new terminal)*

```bash
cd usecases_examples/Railway
source .venv/bin/activate
python app.py
```

Ready when you see: `Running on http://0.0.0.0:5001`

### 7. Start ZWL Angular frontend *(new terminal)*

```bash
cd flatland-hmi-hack4rail/frontend
npm install    # first time only
npm start
```

Ready when you see: `Local: http://localhost:4200`

---

## Railway Use Case

The Railway use case (FHNW/AI4REALNET) adds a Flatland train simulation with three interactive training scenarios:

| ID | Name | Description |
|----|------|-------------|
| `scenario1` | Kreuzungskonflikt | Single-track crossing conflict |
| `scenario2` | Fahrt auf Sichtweite | Speed restriction causing dispatch conflict |
| `scenario3` | Zugreihenfolge | Multiple delays disrupting train order |

Log in as `railway_user` / `test` and select the Railway use case.

---

## Server Deployment

For server deployment, Flask and the ZWL Angular frontend can be containerised — no Python or npm needed on the server.

```bash
# Set server URL before building:
# VITE_RAILWAY_SIMU=http://<SERVER_PUBLIC_IP>:5001

docker compose \
  -f config/dev/cab-standalone/docker-compose.yml \
  -f config/dev/cab-standalone/docker-compose-railway.yml \
  up --build
```

**Provided Dockerfiles:**
- `usecases_examples/Railway/Railway.Dockerfile`
- `flatland-hmi-hack4rail/zwl.Dockerfile`

**⚠️ Open items:** Port 5001 must be reachable from users' browsers. Set `VITE_RAILWAY_SIMU` to the server's public IP/hostname. Disable `AUTH_DISABLED=true` for production.

See `HANDOVER.md` for full details.

---

## Authentication

| Username | Password |
|----------|----------|
| `railway_user` | `test` |
| `powergrid_user` | `test` |
| `atm_user` | `test` |
| `admin` | `test` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Kartenansicht: "cannot connect to localhost:4200" | ZWL Angular not running — run step 7 |
| No train data visible | Flask not running — run step 6 |
| No notification cards | Re-run step 4 (MongoDB command) |
| Build fails: `session.ts` error | `sed -i "s/authStore.logout('json', { force: false })/authStore.logout('json')/" frontend/src/utils/session.ts` |
| Build fails: `stopContext` error | Add `stopContext: () => {}` to `return {}` block in `frontend/src/stores/services.ts` |
| Keycloak crash | `docker compose -f config/dev/cab-standalone/docker-compose.yml up --force-recreate keycloak` |
| MongoDB crash | `docker tag cab-standalone-frontend:latest irtsystemx/interactiveai-cab-standalone-frontend:latest && docker compose -f config/dev/cab-standalone/docker-compose.yml up` |
