#!/usr/bin/env bash
#
# setup.sh — one-shot local setup for the InteractiveAI backend + PowerGrid simulator.
#
# Ported from interactiveai-a3s-integration/setup.sh and adapted to this repo's
# current architecture:
#   - no a3s-service / local RL agent: PowerGrid recommendations combine the
#     external RL agent API (RL_AGENT_API_URL, proxied same-origin via
#     /rl-api/) with the ontology recommender in recommendation-service.
#   - the PowerGrid simulator's mailbox is reached same-origin through the
#     frontend gateway at /powergrid-simu/, not a separate host:5100 URL.
#
# Steps automated:
#   1. Start the InteractiveAI backend (cab-standalone compose)
#   2. Wait for Keycloak + the frontend gateway to come up
#   3. Configure Keycloak (realm Frontend URL) via the admin REST API — no
#      manual admin-console clicking. Falls back to a manual prompt only if
#      the API call fails.
#   4. Load OperatorFabric resources / register use cases / assign entities
#   5. Build and start the PowerGrid simulator
#
# Usage:
#   ./setup.sh                   # full setup (prompts if containers already run)
#   ./setup.sh --clean           # tear down existing containers first, no prompt
#   ./setup.sh --wipe            # tear down existing containers AND volumes, no prompt
#
# Overridable via environment:
#   KC_ADMIN (admin)  KC_PW (admin)  FRONTEND_URL (http://localhost:3200)
#
# Secrets (RL_AGENT_API_URL / RL_AGENT_API_TOKEN / VITE_COGNITIVE_TOKEN) are
# read from config/dev/cab-standalone/.secrets if present (see .secrets.example);
# docker-compose.sh falls back to safe defaults otherwise.

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/config/dev/cab-standalone"
RESOURCES_DIR="$REPO_ROOT/resources"
SIM_DIR="$REPO_ROOT/usecases_examples/PowerGrid"

KC_BASE="http://localhost:89/auth"      # Keycloak 16.x (legacy /auth base path)
KC_REALM="dev"
KC_CLIENT="opfab-client"
KC_ADMIN="${KC_ADMIN:-admin}"
KC_PW="${KC_PW:-admin}"

FRONTEND_URL="${FRONTEND_URL:-http://localhost:3200}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m    ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m    ✗ %s\033[0m\n' "$*" >&2; exit 1; }

# Emit an OSC 8 terminal hyperlink so URLs are clickable even in terminals that
# don't auto-detect bare "localhost" URLs. Degrades to plain text where the
# escape isn't supported (the URL is used as the visible label either way).
link() { printf '\033]8;;%s\033\\%s\033]8;;\033\\' "$1" "$1"; }

# Block until an HTTP endpoint answers with the wanted status, or time out.
wait_for_http() {
  local url="$1" want="${2:-200}" tries="${3:-90}" i=1 code
  while (( i <= tries )); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" || true)"
    [[ "$code" == "$want" ]] && return 0
    printf '    waiting for %s (%s/%s, last=%s)\r' "$url" "$i" "$tries" "$code"
    sleep 2; (( i++ ))
  done
  printf '\n'; return 1
}

require() { command -v "$1" >/dev/null 2>&1 || die "'$1' is required but not installed."; }

# ---------------------------------------------------------------------------
# Keycloak configuration via the admin REST API
# ---------------------------------------------------------------------------
kc_admin_token() {
  curl -s --max-time 10 -X POST \
    "$KC_BASE/realms/master/protocol/openid-connect/token" \
    -d client_id=admin-cli -d "username=$KC_ADMIN" -d "password=$KC_PW" \
    -d grant_type=password \
    | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null
}

# Returns 0 on success, non-zero if anything went wrong (caller then prompts).
kc_configure() {
  local token realm updated code
  token="$(kc_admin_token)"
  [[ -n "$token" ]] || { warn "could not obtain a Keycloak admin token"; return 1; }

  # Set the realm Frontend URL — without it, token issuer URLs don't match what
  # the backend expects and every authenticated call returns 401. (The client
  # redirect URIs / web origins already ship correct in the dev-realm export.)
  realm="$(curl -s --max-time 10 -H "Authorization: Bearer $token" "$KC_BASE/admin/realms/$KC_REALM")"
  updated="$(printf '%s' "$realm" | FRONTEND_URL="$FRONTEND_URL" python3 -c '
import sys, json, os
d = json.load(sys.stdin)
attrs = d.get("attributes") or {}
attrs["frontendUrl"] = os.environ["FRONTEND_URL"]
d["attributes"] = attrs
print(json.dumps(d))' 2>/dev/null)"
  [[ -n "$updated" ]] || { warn "could not read/patch the '$KC_REALM' realm"; return 1; }
  code="$(curl -s -o /dev/null -w '%{http_code}' -X PUT \
    "$KC_BASE/admin/realms/$KC_REALM" \
    -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
    -d "$updated")"
  [[ "$code" == 2* ]] || { warn "realm update returned HTTP $code"; return 1; }
  ok "realm '$KC_REALM' Frontend URL set to $FRONTEND_URL"
  return 0
}

# Manual fallback: pause the script and let the operator configure Keycloak by
# hand.
kc_manual_prompt() {
  cat <<EOF

  ------------------------------------------------------------------
  Automated Keycloak configuration did not complete. Please do it
  manually now:

    1. Open  $KC_BASE/admin   (login: $KC_ADMIN / $KC_PW)
    2. Select the '$KC_REALM' realm
    3. Realm Settings -> General -> Frontend URL = $FRONTEND_URL  -> Save
    4. Clients -> '$KC_CLIENT' -> Valid Redirect URIs must include
       ${FRONTEND_URL%/}/*   (and Web Origins ${FRONTEND_URL})  -> Save
  ------------------------------------------------------------------
EOF
  read -r -p "  Press ENTER once Keycloak is configured to continue... " _
}

# ---------------------------------------------------------------------------
# Existing-container detection / teardown
# ---------------------------------------------------------------------------
# List running containers of the compose project rooted at $1, one
# "  name  (status)" line each (empty output means none are running).
compose_running() {
  ( cd "$1" && docker compose ps --format '      {{.Name}}  ({{.Status}})' 2>/dev/null ) || true
}

# Remove both compose stacks. $1 = extra `down` args (e.g. "-v" to drop volumes).
teardown_stacks() {
  local extra="${1:-}"
  log "Tearing down existing containers${extra:+ and volumes} for a clean rebuild"
  ( cd "$SIM_DIR" && docker compose down $extra 2>/dev/null ) || true
  ( cd "$BACKEND_DIR" && docker compose down $extra 2>/dev/null ) || true
  ok "existing containers removed"
}

# If any of our containers are already running, ask what to do. $1 is the mode
# decided by flags: "" ask, "clean" down, "wipe" down -v.
handle_existing_containers() {
  local mode="${1:-}" running
  running="$(compose_running "$BACKEND_DIR"; compose_running "$SIM_DIR")"

  if [[ -z "$running" ]]; then
    ok "no existing project containers running"
    return 0
  fi

  warn "Found running containers from this setup:"
  printf '%s\n' "$running"

  case "$mode" in
    clean) teardown_stacks ""   ; return 0 ;;
    wipe)  teardown_stacks "-v" ; return 0 ;;
  esac

  if [[ ! -t 0 ]]; then
    warn "non-interactive shell and no --clean/--wipe flag: leaving containers as-is"
    return 0
  fi

  local reply
  read -r -p "  Kill them and rebuild clean?  [y]es  /  [w]ipe data too  /  [N]o, keep running: " reply
  case "${reply,,}" in
    y|yes)  teardown_stacks ""   ;;
    w|wipe) teardown_stacks "-v" ;;
    *)      warn "leaving existing containers in place (continuing)" ;;
  esac
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  local CLEAN_MODE=""
  for arg in "$@"; do
    case "$arg" in
      --clean)   CLEAN_MODE="clean" ;;
      --wipe)    CLEAN_MODE="wipe" ;;
      -h|--help) sed -n '3,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
      *)         die "unknown argument: $arg (see --help)" ;;
    esac
  done

  log "Checking prerequisites"
  require docker; require curl; require python3
  docker compose version >/dev/null 2>&1 || die "'docker compose' (v2) is required."
  ok "docker, docker compose, curl, python3 present"

  if [[ ! -f "$BACKEND_DIR/.secrets" ]]; then
    warn "no config/dev/cab-standalone/.secrets file — using default RL agent API and no cognitive token"
    warn "copy .secrets.example to .secrets to override (see docker-compose.sh)"
  fi

  log "Checking for existing containers"
  handle_existing_containers "$CLEAN_MODE"

  log "Step 1/5 — Starting the InteractiveAI backend"
  ( cd "$BACKEND_DIR" && ./docker-compose.sh )
  ok "backend compose brought up"

  # docker-compose.sh does `up -d` WITHOUT --build, so an existing image is
  # reused as-is. Force a rebuild from THIS repo's source (cache-aware:
  # unchanged sources hit the layer cache and return instantly) so a stale
  # image from a different branch/checkout can't leak its baked-in code.
  log "Rebuilding frontend + recommendation-service from this repo's source"
  ( cd "$BACKEND_DIR" && docker compose build frontend cabrecommendation \
      && docker compose up -d frontend cabrecommendation )
  ok "frontend and recommendation-service rebuilt from source"

  log "Step 2/5 — Waiting for Keycloak"
  wait_for_http "$KC_BASE/realms/master" 200 || die "Keycloak did not come up on :89"
  ok "Keycloak is up"

  log "Step 3/5 — Configuring Keycloak"
  if kc_configure; then
    ok "Keycloak configured automatically"
  else
    kc_manual_prompt
  fi
  log "Restarting the frontend to pick up the Keycloak change"
  docker restart frontend >/dev/null && ok "frontend restarted"
  wait_for_http "$FRONTEND_URL/" 200 || warn "frontend not answering 200 yet (continuing)"

  log "Step 4/5 — Loading resources and registering use cases"
  # Wait until auth actually works end-to-end before loading (avoids 401s).
  local i=1
  until curl -s --max-time 5 -X POST \
      -d "username=admin&password=test&grant_type=password&client_id=$KC_CLIENT" \
      "$FRONTEND_URL/auth/token" | grep -q access_token; do
    (( i > 24 )) && die "auth never became ready ($FRONTEND_URL/auth/token)"
    printf '    waiting for auth to be ready (%s/24)\r' "$i"; sleep 5; (( i++ ))
  done
  printf '\n'; ok "auth is ready"
  ( cd "$RESOURCES_DIR" && ./loadTestConf.sh )
  ok "resources loaded, use cases registered, entities assigned to publisher_test"

  log "Step 5/5 — Building and starting the PowerGrid simulator"
  ( cd "$SIM_DIR" && docker compose up -d --build app )
  ok "PowerGrid simulator started"

  printf '\n\033[1;32mSetup complete.\033[0m\n\n'
  printf '  InteractiveAI UI      %s        (publisher_test / test)\n' "$(link "$FRONTEND_URL")"
  printf '  PowerGrid simulator   %s        (also proxied same-origin at %s/powergrid-simu/)\n' "$(link "http://localhost:5100")" "$FRONTEND_URL"
  printf '  Keycloak admin        %s   (admin / admin)\n' "$(link "$KC_BASE/admin")"
  printf '\n  In the simulator, pick server  %s  and log in.\n' "$(link "http://host.docker.internal:3200/")"
}

main "$@"
