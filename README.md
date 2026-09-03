# InteractiveAI Assistant Platform
**An interactive AI Assistant Platform for Real Time operations**

_Frontend_ 
​ [![Node](https://img.shields.io/badge/Node-339933?style=plastic&logo=nodedotjs&logoColor=fff)](https://nodejs.org) [![Vue](https://img.shields.io/badge/Vue-35495E?style=plastic&logo=vuedotjs&logoColor=fff)](https://vuejs.org) [![Vite](https://img.shields.io/badge/Vite-%23646CFF.svg?style=plastic&logo=vite&logoColor=fff)](https://vitejs.dev) [![TypeScript](https://img.shields.io/badge/Typescript-%23007ACC.svg?style=plastic&logo=typescript&logoColor=fff)](https://www.typescriptlang.org)

_Backend_ 
![Python](https://img.shields.io/badge/python-3670A0?style=plastic&logo=python&logoColor=ffdd54)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=plastic&logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=plastic&logo=docker&logoColor=white)

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#railway-use-case">Railway Use Case</a></li>
    <li><a href="#development">Development</a></li>
  </ol>
</details>

## About The Project

InteractiveAI platform provides support in augmented decision-making for complex steering systems. It is a prototype of a bi-directional virtual assistant, open in terms of industrial applications, in which it will be possible to evaluate the forms of exchange between the expert and an AI that learns continuously.

The platform uses **OperatorFabric** for notification management and is generic — it supports multiple use cases including **PowerGrid**, **ATM**, and **Railway**.

## Getting Started

### Prerequisites

- [Git](https://git-scm.com/)
- [Docker Engine 27+](https://www.docker.com/)
- [Docker Compose V2](https://www.docker.com/)
- **Railway use case only:** Python 3.10, Node.js 18+ (see [Railway Use Case](#railway-use-case))

### Setup

```sh
git clone [repo-url]
cd InteractiveAI
git checkout FHNWtec-version   # Railway use case branch

cp config/dev/cab-standalone/.env.example config/dev/cab-standalone/.env
```

Edit `.env` and set simulator URLs:
```sh
VITE_RAILWAY_SIMU=http://localhost:5001    # or server IP for deployment
VITE_POWERGRID_SIMU=
VITE_ATM_SIMU=
```

## Usage

### Running All Services (Dev Mode)

```sh
export USER_ID=1000 USER_GID=1000
export SPRING_PROFILES_ACTIVE=docker
export VITE_RAILWAY_SIMU=http://localhost:5001

docker compose -f config/dev/cab-standalone/docker-compose.yml up
```

Then load resources:
```sh
cd resources && ./loadTestConf.sh
```

### Default Ports

| Service | Port |
|---------|------|
| Frontend | 3200 |
| Railway brain (Flask) | 5001 |
| ZWL Angular (Railway) | 4200 |
| Keycloak | 89 |

### Authentication

| Username | Password |
|----------|----------|
| `railway_user` | `test` |
| `powergrid_user` | `test` |
| `admin` | `test` |

---

## Railway Use Case

The Railway use case adds a Flatland train simulation with interactive scenario-based training. It requires **two additional services** beyond the main Docker stack.

> See **[HANDOVER.md](HANDOVER.md)** for full deployment details.

### Additional Prerequisites

- **Python 3.10** (exact version required for flatland-rl)
- **Node.js 18+**

### Option A — Local / Development

Start the main Docker stack (see [Usage](#usage)), then:

**Terminal 2 — Flask Railway brain:**
```sh
cd usecases_examples/Railway
python3.10 -m venv .venv
source .venv/bin/activate      # Linux/Mac | .venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
```
Ready when: `Running on http://0.0.0.0:5001`

**Terminal 3 — ZWL Angular frontend:**
```sh
cd flatland-hmi-hack4rail/frontend
npm install    # first time only
npm start
```
Ready when: `Local: http://localhost:4200`

**MongoDB perimeter setup** (required after every Docker restart):
```sh
docker exec cab-standalone-mongodb-1 mongo operator-fabric \
  -u root -p password --authenticationDatabase admin \
  --eval 'db.perimeter.updateOne({_id:"cabProcess"},{$set:{process:"cabProcess",stateRights:[{state:"messageState",right:"ReceiveAndWrite"}]}},{upsert:true}); db.group.updateOne({_id:"Planner"},{$addToSet:{perimeters:"cabProcess"}}); db.group.updateOne({_id:"Dispatcher"},{$addToSet:{perimeters:"cabProcess"}}); print("done")'
```

### Option B — Server / Production (Docker)

Flask and the ZWL Angular frontend can be containerised using the provided Dockerfiles, eliminating the need for Python or npm on the server.

```sh
# Set server URL in .env:
# VITE_RAILWAY_SIMU=http://<SERVER_PUBLIC_IP>:5001

docker compose \
  -f config/dev/cab-standalone/docker-compose.yml \
  -f config/dev/cab-standalone/docker-compose-railway.yml \
  up --build
```

**Provided deployment files:**
- `usecases_examples/Railway/Railway.Dockerfile` — Flask container
- `flatland-hmi-hack4rail/zwl.Dockerfile` — Angular/nginx container
- `config/dev/cab-standalone/docker-compose-railway.yml` — adds both to the stack
- `config/dev/cab-standalone/mongo-init.js` — auto-applies MongoDB perimeter

**⚠️ Open items for server deployment:**
1. Port 5001 must be reachable from users' browsers (open firewall or nginx proxy)
2. `AUTH_DISABLED=true` must be removed for production
3. Set `VITE_RAILWAY_SIMU` to the server's public IP/hostname before building

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Kartenansicht: "cannot connect to localhost:4200" | Start the ZWL Angular frontend (Terminal 3) |
| No train data visible | Flask brain not running — start Terminal 2 |
| No notification cards | Run MongoDB perimeter command above |
| Build fails: `session.ts` error | `sed -i "s/authStore.logout('json', { force: false })/authStore.logout('json')/" frontend/src/utils/session.ts` |
| Build fails: `stopContext` error | Add `stopContext: () => {}` to the `return {}` block in `frontend/src/stores/services.ts` |
| Keycloak crash | `docker compose -f config/dev/cab-standalone/docker-compose.yml up --force-recreate keycloak` |

---

## Development

Contributions welcome — please follow the [developer guide](docs/developer-guide.md).

A Postman collection is available under `docs/postman_collections`.
