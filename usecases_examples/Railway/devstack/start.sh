#!/usr/bin/env bash
# Start the Railway dev stack without Docker: the Event, Context, Historic and Recommendation
# services on SQLite (AUTH_DISABLED), registered for Railway, and the Railway simulator, behind the
# dev gateway on port 3200. Stops everything on Ctrl-C. Never expose it beyond localhost.
#
# Settings (environment):
#   FRONTEND        dist (default): serve FRONTEND_DIST (default frontend/dist, build it first)
#                   vite: start the Vite dev server in FRONTEND_DIR (default frontend), with HMR
#                   none: the frontend is started elsewhere and reached at VITE_URL
#   DEVSTACK_PYTHON python with requirements.txt installed; default: a venv per OS and CPU under
#                   DEVSTACK_HOME, created on first start from Python 3.11 or 3.12 (the services
#                   run 3.11; their pinned SQLAlchemy 2.0.16 fails on 3.13 and later)
#   DEVSTACK_BASE_PYTHON  the Python 3.11/3.12 to create that venv from, if neither python3.11,
#                   python3.12 nor python3 on PATH is one
#   DEVSTACK_HOME   where the venv, the SQLite files and the logs go
#                   (default .cache/railway-devstack in the repo root, gitignored)
#   GATEWAY_PORT    default 3200
#   RAILWAY_STEPS_PER_SECOND  the simulator's pace (default 1; e.g. 4 for quick checks)
#   RAILWAY_SIM_PYTHON  python with usecases_examples/Railway/requirements.txt (Flatland) installed;
#                   default: a second venv per OS and CPU under DEVSTACK_HOME, made like the first
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
DEVSTACK_HOME="${DEVSTACK_HOME:-$ROOT/.cache/railway-devstack}"
DATA="$DEVSTACK_HOME/data"
LOGS="$DEVSTACK_HOME/logs"
export FRONTEND="${FRONTEND:-dist}"
export GATEWAY_PORT="${GATEWAY_PORT:-3200}"
export VITE_URL="${VITE_URL:-http://127.0.0.1:5173}"
mkdir -p "$DATA" "$LOGS"

# --- Python for the services and the gateway
py_version() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }
supported() { [[ "$1" == 3.11 || "$1" == 3.12 ]]; }

base_python() {
    local BASE="${DEVSTACK_BASE_PYTHON:-}"
    if [[ -z "$BASE" ]]; then
        for candidate in python3.11 python3.12 python3; do
            if command -v "$candidate" >/dev/null && supported "$(py_version "$candidate")"; then
                BASE="$candidate"
                break
            fi
        done
    fi
    if [[ -z "$BASE" ]] || ! supported "$(py_version "$BASE")"; then
        echo "The dev stack needs Python 3.11 or 3.12 (the services' pins fail on 3.13 and later)." >&2
        echo "Install one (e.g. conda create -n py311 python=3.11, brew install python@3.11) and set" >&2
        echo "DEVSTACK_BASE_PYTHON to it, or put python3.11 on PATH." >&2
        exit 1
    fi
    echo "$BASE"
}

make_venv() {   # venv requirements; prints the venv's python
    local VENV="$1" REQS="$2" BASE
    if [[ -x "$VENV/bin/python" ]] && ! supported "$(py_version "$VENV/bin/python")"; then
        echo "recreating $VENV: made with Python $(py_version "$VENV/bin/python")" >&2
        rm -rf "$VENV"
    fi
    if [[ ! -x "$VENV/bin/python" ]]; then
        BASE="$(base_python)"
        echo "creating $VENV with $BASE (Python $(py_version "$BASE"))" >&2
        "$BASE" -m venv "$VENV"
    fi
    if ! cmp -s "$REQS" "$VENV/.requirements.txt"; then
        "$VENV/bin/python" -m pip install -q -r "$REQS" >&2
        cp "$REQS" "$VENV/.requirements.txt"
    fi
    echo "$VENV/bin/python"
}

# host and container may share the checkout, so one venv per OS and CPU
PY="${DEVSTACK_PYTHON:-$(make_venv "$DEVSTACK_HOME/venv-$(uname -s)-$(uname -m)" "$HERE/requirements.txt")}"
SIM="$ROOT/usecases_examples/Railway"
SIM_PY="${RAILWAY_SIM_PYTHON:-$(make_venv "$DEVSTACK_HOME/venv-sim-$(uname -s)-$(uname -m)" "$SIM/requirements.txt")}"

PIDS=()
stop() {
    trap - INT TERM EXIT
    echo "stopping the dev stack"
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
}
trap stop INT TERM EXIT

wait_for() {   # name url
    for _ in $(seq 1 60); do
        if curl -fs -o /dev/null "$2"; then return 0; fi
        sleep 0.5
    done
    echo "$1 did not start, see $LOGS/$1.log" >&2
    exit 1
}

# --- platform services (host ports of config/dev/cab-standalone/docker-compose.yml)
start_service() {   # dir port
    local name="$1" port="$2"
    (
        cd "$ROOT/backend/$name"
        exec env FLASK_APP="app:create_app('dev')" \
            DATABASE_URL="sqlite:///$DATA/$name.db" \
            AUTH_DISABLED=true DEFAULT_USE_CASE=Railway \
            CARDS_PUBLICATION_SERVICE="http://127.0.0.1:$GATEWAY_PORT/cardspub" \
            GATEWAY_SERVICE="http://127.0.0.1:$GATEWAY_PORT" \
            HISTORIC_SERVICE="http://127.0.0.1:5200" \
            PYTHONPATH="$ROOT/backend/cab_common" PYTHONDONTWRITEBYTECODE=1 \
            "$PY" -m flask run --host 127.0.0.1 --port "$port"
    ) >"$LOGS/$name.log" 2>&1 &
    PIDS+=($!)
}

start_service event-service 5000
start_service context-service 5100
start_service historic-service 5200
start_service recommendation-service 5400

"$PY" -B "$HERE/gateway.py" >"$LOGS/gateway.log" 2>&1 &
PIDS+=($!)

# --- the Railway simulator, reached at /railway-simu/ through the gateway; it posts its events and
# contexts through the gateway too, as on the server through the platform's nginx
(
    cd "$SIM"
    exec env RAILWAY_PLATFORM_URL="http://127.0.0.1:$GATEWAY_PORT" \
        RAILWAY_STEPS_PER_SECOND="${RAILWAY_STEPS_PER_SECOND:-1}" \
        RAILWAY_SIMU_HOST=127.0.0.1 RAILWAY_SIMU_PORT=5124 PYTHONDONTWRITEBYTECODE=1 \
        "$SIM_PY" app.py
) >"$LOGS/railway-simulator.log" 2>&1 &
PIDS+=($!)

if [[ "$FRONTEND" == vite ]]; then
    (cd "${FRONTEND_DIR:-$ROOT/frontend}" && exec env VITE_RAILWAY_SIMU=/railway-simu npx vite --host 127.0.0.1 --port 5173 --strictPort) \
        >"$LOGS/vite.log" 2>&1 &
    PIDS+=($!)
fi

wait_for event-service http://127.0.0.1:5000/api/v1/health
wait_for context-service http://127.0.0.1:5100/api/v1/health
wait_for historic-service http://127.0.0.1:5200/api/v1/health
wait_for recommendation-service http://127.0.0.1:5400/api/v1/health
wait_for gateway "http://127.0.0.1:$GATEWAY_PORT/users/CurrentUserWithPerimeters"
wait_for railway-simulator http://127.0.0.1:5124/health

# --- register Railway in the three services (as resources/loadTestConf.sh); a repeat is refused
for svc in "cab_event resources/cabUsecasesEvent/RailwayEvent.json" \
           "cabcontext resources/cabUsecasesContext/RailwayContext.json" \
           "cab_recommendation resources/cabUsecasesRecommendation/RailwayRecommendationUC.json"; do
    set -- $svc
    curl -s -o /dev/null -X POST "http://127.0.0.1:$GATEWAY_PORT/$1/api/v1/usecases" \
        -H "Content-Type: application/json" --data @"$ROOT/$2" || true
done

echo "dev stack on http://localhost:$GATEWAY_PORT (frontend: $FRONTEND, logs: $LOGS); Ctrl-C stops it"
wait
