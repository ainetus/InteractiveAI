#!/usr/bin/env bash
#
# local_setup.sh — one-shot local setup for the InteractiveAI backend + PowerGrid simulator.
#
# Steps: start the backend, wait for Keycloak + frontend, configure Keycloak via
# the admin REST API (manual prompt as fallback), load OperatorFabric resources,
# build and start the PowerGrid simulator, reload the frontend nginx and verify
# the recommendation path.
#
# Usage:
#   ./local_setup.sh                   # full setup (prompts if containers already run)
#   ./local_setup.sh --clean           # tear down existing containers first, no prompt
#   ./local_setup.sh --wipe            # tear down existing containers AND volumes, no prompt
#   ./local_setup.sh --a3s [URL]       # take recommendations from an already-running A3S
#                                      # (default URL http://host.docker.internal:5010/api/v1/recommendation)
#
# This script never starts A3S. Start it first from a3s-service/ with
# ./docker/local_setup.sh, then pass --a3s here.
#
# Overridable via environment:
#   KC_ADMIN (admin)  KC_PW (admin)  FRONTEND_URL (http://localhost:3200)
#
# Secrets (RL_AGENT_API_URL / RL_AGENT_API_TOKEN / COGNITIVE_TOKEN) are read from
# config/dev/cab-standalone/.secrets if present (see .secrets.example).

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/config/dev/cab-standalone"
RESOURCES_DIR="$REPO_ROOT/resources"
SIM_DIR="$REPO_ROOT/usecases_examples/PowerGrid"
SIM_COMPOSE="docker-compose.local.yml"   # server config lives in docker-compose.yml
SIM_PORT=5122                            # must match POWERGRID_SIMU_UPSTREAM in .env
# Where --a3s points the recommendation service when no URL is given. host.docker.internal
# is how the containers reach a service published on the host.
A3S_DEFAULT_URL="http://host.docker.internal:5010/api/v1/recommendation"
# Serializer name the simulator stamps into environment_state; must match what A3S accepts.
SIM_SERIALIZER_SRC="$REPO_ROOT/usecases_examples/PowerGrid/app/models/env_serialization.py"

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

# Emit an OSC 8 terminal hyperlink; degrades to plain text if unsupported.
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

# True if $1 is the name of a currently running container.
container_running() { docker ps --format '{{.Names}}' | grep -qx "$1"; }

# ---------------------------------------------------------------------------
# Gateway / A3S robustness
# ---------------------------------------------------------------------------
# nginx caches upstream IPs at config load, so a container recreated afterwards
# 502s until reloaded. Reload against the substituted config (-c), not the raw
# templated one nginx -s reload would otherwise validate.
frontend_nginx_reload() {
  container_running frontend || { warn "frontend not running — skipping nginx reload"; return 0; }
  if docker exec frontend nginx -c /personal-conf/nginx.conf -s reload >/dev/null 2>&1; then
    ok "frontend nginx reloaded (upstream IPs re-resolved)"
  elif docker exec frontend nginx -s reload >/dev/null 2>&1; then
    ok "frontend nginx reloaded"
  else
    warn "nginx reload failed — restarting the frontend container instead"
    docker restart frontend >/dev/null 2>&1 || { warn "frontend restart failed"; return 0; }
    wait_for_http "$FRONTEND_URL/" 200 >/dev/null || warn "frontend not answering 200 yet"
    ok "frontend restarted"
  fi
}

# --a3s: A3S runs on its own (a3s-service/docker/local_setup.sh), so all this
# does is point the recommendation service at it — after confirming it answers,
# because otherwise the only symptom is an empty recommendation panel at the end
# of a ten-minute setup.
require_a3s() {
  local health="${RL_AGENT_API_URL%/recommendation}/health"
  # The containers reach it via host.docker.internal; from here it is localhost.
  local host_health="${health/host.docker.internal/localhost}"
  if wait_for_http "$host_health" 200 3 >/dev/null; then
    ok "A3S is answering at $host_health"
    return 0
  fi
  warn "no A3S answering at $host_health"
  warn "  start it first:  cd $REPO_ROOT/a3s-service && ./docker/local_setup.sh"
  warn "  or pass the URL: ./local_setup.sh --a3s http://host.docker.internal:<port>/api/v1/recommendation"
  die "A3S is not running"
}

# Checks the gateway route, the RL agent, and the simulator/A3S serializer contract.
verify_recommendation_path() {
  local failures=0

  if wait_for_http "$FRONTEND_URL/cab_recommendation/api/v1/health" 200 15 >/dev/null; then
    ok "gateway route $FRONTEND_URL/cab_recommendation/ reaches the recommendation service"
  else
    warn "gateway route to the recommendation service is not answering 200"
    warn "  the browser calls it at /cab_recommendation/ — a 502 here means a stale nginx upstream"
    failures=$(( failures + 1 ))
  fi

  if [[ -n "${RL_AGENT_API_URL:-}" ]]; then
    # Resolve from inside the recommendation container, whose network namespace RL_AGENT_API_URL targets.
    local health_url="${RL_AGENT_API_URL%/recommendation}/health"
    if container_running cab_recommendation && docker exec cab_recommendation python -c "
import sys, urllib.request, ssl
ctx = ssl._create_unverified_context()
try:
    urllib.request.urlopen('$health_url', timeout=8, context=ctx)
except Exception as e:
    sys.exit(str(e) or 'unreachable')
" >/dev/null 2>&1; then
      ok "RL agent reachable from cab_recommendation at $health_url"
      # May point at a standalone A3S on the host; find it by its published port.
      local port a3s_container
      port="$(sed -E 's#.*://[^/:]+:([0-9]+).*#\1#' <<<"$RL_AGENT_API_URL")"
      if [[ "$port" =~ ^[0-9]+$ ]]; then
        a3s_container="$(docker ps --format '{{.Names}}\t{{.Ports}}' \
                          | awk -F'\t' -v p=":$port->" 'index($2, p) {print $1; exit}')"
        if [[ -n "$a3s_container" ]]; then
          verify_serializer_contract "$a3s_container" || failures=$(( failures + 1 ))
        fi
      fi
    else
      warn "RL agent at \$RL_AGENT_API_URL is NOT reachable from inside cab_recommendation"
      warn "  URL: $RL_AGENT_API_URL"
      warn "  a container on another compose network is not reachable by name —"
      warn "  use http://host.docker.internal:<published-port>/api/v1/recommendation"
      failures=$(( failures + 1 ))
    fi
  else
    warn "RL_AGENT_API_URL is not set — only the ontology recommender will run"
  fi

  return "$failures"
}

# Compares the simulator's serializer name against what A3S accepts.
# $1 = name of the container running A3S.
verify_serializer_contract() {
  local a3s="$1" emitted accepted
  emitted="$(grep -oE '"serializer": [A-Z0-9_]+' "$SIM_SERIALIZER_SRC" 2>/dev/null | awk '{print $2}' | head -1)"
  [[ -n "$emitted" ]] || { warn "could not determine the simulator's serializer from $SIM_SERIALIZER_SRC"; return 0; }
  emitted="$(grep -oE "^${emitted} = \"[a-z0-9_]+\"" "$SIM_SERIALIZER_SRC" | sed 's/.*"\(.*\)"/\1/' | head -1)"
  [[ -n "$emitted" ]] || { warn "could not resolve the simulator's serializer constant"; return 0; }

  accepted="$(docker exec "$a3s" sh -c 'grep -hoE "grid2op_observation_v[0-9]+" /my_app/integrations/powergrid/serialization.py 2>/dev/null | sort -u' 2>/dev/null || true)"
  if [[ -z "$accepted" ]]; then
    warn "could not read the serializers '$a3s' accepts — skipping the contract check"
    return 0
  fi
  if grep -qx "$emitted" <<<"$accepted"; then
    ok "serializer contract OK — simulator emits '$emitted', '$a3s' accepts it"
    return 0
  fi
  warn "SERIALIZER MISMATCH — recommendations will silently come back empty"
  warn "  simulator emits:      $emitted"
  warn "  '$a3s' accepts: $(tr '\n' ' ' <<<"$accepted")"
  warn "  that A3S image predates the simulator's payload format — rebuild it:"
  warn "    cd $REPO_ROOT/a3s-service && ./docker/local_setup.sh --rebuild"
  return 1
}

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

  # Without a matching Frontend URL, token issuer URLs mismatch and auth returns 401.
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

# Manual fallback: pause and let the operator configure Keycloak by hand.
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
# Lists running containers of the compose project rooted at $1. $2 = optional compose file.
compose_running() {
  ( cd "$1" && docker compose ${2:+-f "$2"} ps --format '      {{.Name}}  ({{.Status}})' 2>/dev/null ) || true
}

# Remove both compose stacks. $1 = extra `down` args (e.g. "-v" to drop volumes).
teardown_stacks() {
  local extra="${1:-}"
  log "Tearing down existing containers${extra:+ and volumes} for a clean rebuild"
  ( cd "$SIM_DIR" && docker compose -f "$SIM_COMPOSE" down $extra 2>/dev/null ) || true
  ( cd "$BACKEND_DIR" && docker compose down $extra 2>/dev/null ) || true
  ok "existing containers removed"
}

# Ask what to do if our containers are already running. $1: "" ask, "clean" down, "wipe" down -v.
handle_existing_containers() {
  local mode="${1:-}" running
  running="$(compose_running "$BACKEND_DIR"; compose_running "$SIM_DIR" "$SIM_COMPOSE")"

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
  # Deliberately not named USE_A3S: .secrets is sourced into this scope below,
  # and an old `export USE_A3S=1` there would silently turn this flag on.
  local CLEAN_MODE="" A3S_MODE=0 A3S_URL=""
  while (( $# )); do
    case "$1" in
      --clean)   CLEAN_MODE="clean" ;;
      --wipe)    CLEAN_MODE="wipe" ;;
      # --a3s takes an optional URL: anything that is not another flag.
      --a3s)     A3S_MODE=1
                 [[ "${2:-}" == -* || -z "${2:-}" ]] || { A3S_URL="$2"; shift; } ;;
      -h|--help) sed -n '3,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
      *)         die "unknown argument: $1 (see --help)" ;;
    esac
    shift
  done

  log "Checking prerequisites"
  require docker; require curl; require python3
  docker compose version >/dev/null 2>&1 || die "'docker compose' (v2) is required."
  ok "docker, docker compose, curl, python3 present"

  # Source .secrets in THIS shell too (docker-compose.sh sources it in a
  # subshell), so the verification step below knows which agent is configured.
  if [[ -f "$BACKEND_DIR/.secrets" ]]; then
    # shellcheck disable=SC1091  # path is runtime-resolved, gitignored
    source "$BACKEND_DIR/.secrets"
  else
    warn "no config/dev/cab-standalone/.secrets file — using default RL agent API and no cognitive token"
    warn "copy .secrets.example to .secrets to override (see docker-compose.sh)"
  fi

  # --a3s wins over whatever .secrets says: it is the more explicit statement of
  # where recommendations come from for this run. docker-compose.sh sources
  # .secrets in its own shell, so export it rather than just setting it.
  if (( A3S_MODE )); then
    log "Using A3S for recommendations"
    export RL_AGENT_API_URL="${A3S_URL:-$A3S_DEFAULT_URL}"
    require_a3s
    ok "recommendation service will call $RL_AGENT_API_URL"
  fi

  log "Checking for existing containers"
  handle_existing_containers "$CLEAN_MODE"

  log "Step 1/6 — Starting the InteractiveAI backend"
  ( cd "$BACKEND_DIR" && ./docker-compose.sh )
  ok "backend compose brought up"

  # Force a rebuild from this repo's source: docker-compose.sh's `up -d` reuses
  # existing images as-is, so edits here would otherwise not reach the containers.
  log "Rebuilding frontend and cabrecommendation from this repo's source"
  ( cd "$BACKEND_DIR" && docker compose up -d --build --force-recreate frontend cabrecommendation )
  ok "frontend, cabrecommendation rebuilt from source"

  log "Step 2/6 — Waiting for Keycloak"
  wait_for_http "$KC_BASE/realms/master" 200 || die "Keycloak did not come up on :89"
  ok "Keycloak is up"

  log "Step 3/6 — Configuring Keycloak"
  if kc_configure; then
    ok "Keycloak configured automatically"
  else
    kc_manual_prompt
  fi
  log "Restarting the frontend to pick up the Keycloak change"
  docker restart frontend >/dev/null && ok "frontend restarted"
  wait_for_http "$FRONTEND_URL/" 200 || warn "frontend not answering 200 yet (continuing)"

  log "Step 4/6 — Loading resources and registering use cases"
  # Wait until auth actually works end-to-end before loading (avoids 401s).
  local i=1
  while true; do
    unset token
    source "$RESOURCES_DIR/getToken.sh" admin "${FRONTEND_URL%:*}" >/dev/null 2>&1 || true
    [[ -n "${token:-}" ]] && break
    (( i > 24 )) && die "auth never became ready ($FRONTEND_URL/auth/token)"
    printf '    waiting for auth to be ready (%s/24)\r' "$i"; sleep 5; (( i++ ))
  done
  printf '\n'; ok "auth is ready"
  ( cd "$RESOURCES_DIR" && ./loadTestConf.sh )
  ok "resources loaded, use cases registered"

  log "Step 5/6 — Building and starting the PowerGrid simulator"
  # The default docker-compose.yml is the server config (wrong port); use the local one.
  ( cd "$SIM_DIR" && docker compose -f "$SIM_COMPOSE" up -d --build --force-recreate app )
  ok "PowerGrid simulator started"

  # Last, once nothing else will be recreated, so the re-resolved upstream IPs stick.
  log "Step 6/6 — Re-pointing the gateway and verifying the recommendation path"
  frontend_nginx_reload
  if verify_recommendation_path; then
    ok "recommendation path verified end to end"
  else
    warn "the recommendation path is NOT fully working — see the warnings above"
    warn "the UI will come up, but the PowerGrid recommendation panel may stay empty"
  fi

  printf '\n\033[1;32mSetup complete.\033[0m\n\n'
  # powergrid_user is provisioned with the PowerGrid entity; publisher_test isn't.
  printf '  InteractiveAI UI      %s        (powergrid_user / test)\n' "$(link "$FRONTEND_URL")"
  printf '  PowerGrid simulator   %s        (powergrid_user / test) (also proxied same-origin at %s/powergrid-simu/)\n' "$(link "http://localhost:$SIM_PORT")" "$FRONTEND_URL"
  printf '  Keycloak admin        %s   (admin / admin)\n' "$(link "$KC_BASE/admin")"
  printf '\n  In the simulator, pick server  %s  and log in.\n' "$(link "http://host.docker.internal:3200/")"
}

main "$@"
