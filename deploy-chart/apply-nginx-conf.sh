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
import json, sys
try:
    import yaml
except ImportError:
    sys.exit('PyYAML missing on this machine: pip install pyyaml')

path = sys.argv[1]
doc = yaml.safe_load(open(path))
if not isinstance(doc, dict) or not isinstance(doc.get('data'), dict):
    sys.exit(
        f'{path} is not a ConfigMap manifest with a data: mapping '
        f'(parsed as {type(doc).__name__}). Is this file up to date? '
        'It must be the version carrying the /powergrid-simu/ block.'
    )
conf = doc['data'].get('nginx.conf')
if not conf:
    sys.exit(f'{path} has no data."nginx.conf" key; found: {sorted(doc["data"])}')
if '/powergrid-simu/' not in conf:
    sys.exit(
        f'{path} nginx.conf has no /powergrid-simu/ location - this copy predates the fix. '
        'Pull the latest revision of the repo.'
    )
if '__COGNITIVE_TOKEN__' not in conf:
    sys.exit(
        f'{path} nginx.conf does not inject __COGNITIVE_TOKEN__ into /cognitive-api/ - this '
        'copy predates the move of the token out of the frontend bundle. Pull the latest '
        'revision of the repo.'
    )
print(json.dumps({'data': {'nginx.conf': conf}}))
PY
)

echo "--- diff (live -> repo) for $NS/$CM nginx.conf"
kubectl -n "$NS" get cm "$CM" -o jsonpath='{.data.nginx\.conf}' > /tmp/nginx.conf.live || true
python3 -c "import json,sys;sys.stdout.write(json.loads(sys.argv[1])['data']['nginx.conf'])" "$PATCH" > /tmp/nginx.conf.repo
diff -u /tmp/nginx.conf.live /tmp/nginx.conf.repo || true

read -r -p "Apply to $NS/$CM and restart $DEPLOY? [y/N] " ans
case "$ans" in
  y|Y|yes|YES|Yes) ;;
  *) echo "ABORTED - nothing was applied."; exit 0 ;;
esac

kubectl -n "$NS" patch cm "$CM" --type merge -p "$PATCH"
kubectl -n "$NS" rollout restart "deploy/$DEPLOY"
kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=180s

# The frontend pod must carry the env vars that start-webui.sh substitutes into the conf's
# __NAME__ placeholders. Without POWERGRID_SIMU_UPSTREAM nginx gets the local-dev default
# (host.docker.internal) and refuses to start; without COGNITIVE_TOKEN the /cognitive-api/
# proxy sends an empty bearer token and the cognitive panel 401s.
echo "--- frontend POWERGRID_SIMU_UPSTREAM:"
kubectl -n "$NS" get "deploy/$DEPLOY" \
  -o jsonpath='{range .spec.template.spec.containers[*].env[?(@.name=="POWERGRID_SIMU_UPSTREAM")]}{.value}{"\n"}{end}'

# Only that the var is wired to a secret - never the value itself.
echo "--- frontend COGNITIVE_TOKEN source:"
kubectl -n "$NS" get "deploy/$DEPLOY" \
  -o jsonpath='{range .spec.template.spec.containers[*].env[?(@.name=="COGNITIVE_TOKEN")]}{.valueFrom.secretKeyRef.name}/{.valueFrom.secretKeyRef.key}{"\n"}{end}' \
  | grep . || echo "MISSING - add it to values.ovh.yaml (secret cab-frontend, key cognitive-token)"

# Verify against the config nginx actually loaded, not against the ConfigMap.
echo "--- verify: /powergrid-simu/ in the running nginx config"
if kubectl -n "$NS" exec "deploy/$DEPLOY" -- nginx -T 2>/dev/null | grep -q "location /powergrid-simu/"; then
  echo "OK - the location is live."
  kubectl -n "$NS" exec "deploy/$DEPLOY" -- nginx -T 2>/dev/null |
    grep -A6 "location /powergrid-simu/"
else
  echo "FAILED - the running nginx still has no /powergrid-simu/ location." >&2
  echo "  ConfigMap key currently in the cluster:" >&2
  kubectl -n "$NS" get cm "$CM" -o jsonpath='{.data.nginx\.conf}' |
    grep -c powergrid-simu >&2 || true
  echo "  (0 above = the patch did not stick, e.g. ArgoCD self-heal reverted it)" >&2
  echo "  Pods (a crashlooping new pod leaves the OLD one serving):" >&2
  kubectl -n "$NS" get pods -l app.kubernetes.io/name=frontend >&2
  exit 1
fi
