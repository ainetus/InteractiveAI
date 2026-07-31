#!/usr/bin/env bash
#
# stop.sh — tear down the local InteractiveAI backend + PowerGrid simulator.
#
# Usage:
#   ./stop.sh            # stop & remove containers, KEEP data volumes (default)
#   ./stop.sh --wipe     # also delete data volumes (Postgres/Mongo/Keycloak) — fresh start next time
#   ./stop.sh --pause    # just stop containers, keep them (fastest; `./setup.sh` or `docker compose start` to resume)
#   ./stop.sh --help
#
# Both Docker Compose projects are handled: the backend (config/dev/cab-standalone)
# and the PowerGrid simulator (usecases_examples/PowerGrid).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/config/dev/cab-standalone"
SIM_DIR="$REPO_ROOT/usecases_examples/PowerGrid"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m    ✓ %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m    ✗ %s\033[0m\n' "$*" >&2; exit 1; }

case "${1:-}" in
  "")               MSG="Stopping everything (containers removed, data volumes kept)"
                    COMPOSE_CMD="down" ;;
  --wipe|--volumes) MSG="Stopping everything and DELETING data volumes (fresh start next time)"
                    COMPOSE_CMD="down -v" ;;
  --pause|--stop)   MSG="Pausing everything (containers kept, resume later)"
                    COMPOSE_CMD="stop" ;;
  -h|--help)        sed -n '3,13p' "${BASH_SOURCE[0]}"; exit 0 ;;
  *)                die "unknown argument: ${1} (see --help)" ;;
esac

# Run the chosen teardown command in a compose project directory.
run() {
  ( cd "$1" && docker compose $COMPOSE_CMD 2>/dev/null ) || true
}

log "$MSG"

# Simulator first, then backend it depends on.
run "$SIM_DIR"
run "$BACKEND_DIR"

ok "done"
