#!/usr/bin/env bash
# Push ONLY the nginx.conf key of configmap-assistant-platform.yaml to the live cluster,
# then restart the frontend so nginx re-reads it (nginx reads conf.d at startup only).
#
# Why a patch and not `kubectl apply -f configmap-assistant-platform.yaml`: that file is a
# dump of the whole ConfigMap (web-ui.json, users.yml, ...). Applying it wholesale would
# also revert any of those keys that drifted in the cluster since the dump was taken.
#
# Usage:  ./deploy-chart/apply-nginx-conf.sh [namespace] [deployment]
set -euo pipefail

NS="${1:-cab}"
DEPLOY="${2:-cab-frontend}"
CM=cab-assistant-platform-config
SRC="$(dirname "$0")/configmap-assistant-platform.yaml"

command -v kubectl >/dev/null || { echo "kubectl not found" >&2; exit 1; }
[ -f "$SRC" ] || { echo "missing $SRC" >&2; exit 1; }

# Repo -> JSON merge patch carrying just the one key.
PATCH=$(python3 - "$SRC" <<'PY'
import json, sys, yaml
conf = yaml.safe_load(open(sys.argv[1]))['data']['nginx.conf']
assert '/powergrid-simu/' in conf, 'repo nginx.conf is missing the /powergrid-simu/ location'
print(json.dumps({'data': {'nginx.conf': conf}}))
PY
)

echo "--- diff (live -> repo) for $NS/$CM nginx.conf"
kubectl -n "$NS" get cm "$CM" -o jsonpath='{.data.nginx\.conf}' > /tmp/nginx.conf.live || true
python3 -c "import json,sys;sys.stdout.write(json.loads(sys.argv[1])['data']['nginx.conf'])" "$PATCH" > /tmp/nginx.conf.repo
diff -u /tmp/nginx.conf.live /tmp/nginx.conf.repo || true

read -r -p "Apply to $NS/$CM and restart $DEPLOY? [y/N] " ans
[ "$ans" = y ] || { echo "aborted"; exit 0; }

kubectl -n "$NS" patch cm "$CM" --type merge -p "$PATCH"
kubectl -n "$NS" rollout restart "deploy/$DEPLOY"
kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=180s

# The frontend pod must carry POWERGRID_SIMU_UPSTREAM: start-webui.sh substitutes it into
# the __POWERGRID_SIMU_UPSTREAM__ placeholder. Without it nginx gets the local-dev default
# (host.docker.internal) and refuses to start.
echo "--- frontend POWERGRID_SIMU_UPSTREAM:"
kubectl -n "$NS" get "deploy/$DEPLOY" \
  -o jsonpath='{range .spec.template.spec.containers[*].env[?(@.name=="POWERGRID_SIMU_UPSTREAM")]}{.value}{"\n"}{end}'

echo "--- verify: must NOT be text/html (SPA fallback) any more"
kubectl -n "$NS" exec "deploy/$DEPLOY" -- \
  sh -c 'grep -c powergrid-simu /personal-conf/conf.d/default.conf' || true
