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

# ---------------------------------------------------------------------------
# Pre-flight: never push a conf ahead of the pod that has to substitute it.
#
# Every __NAME__ placeholder in the conf is substituted at container start by
# start-webui.sh from the matching env var on the pod. Pushing a conf whose
# placeholders the running deployment cannot satisfy breaks the proxy silently,
# and how it breaks depends on the image:
#   - an image whose start-webui.sh knows the name but gets no value substitutes
#     EMPTY - "Bearer " with nothing after it;
#   - an older image that never heard of the name leaves the placeholder to go out
#     LITERALLY in the proxied request.
# nginx starts cleanly either way, so nothing surfaces it but a 401 in the browser.
#
# This is exactly how /cognitive-api/ broke: the ConfigMap gained __COGNITIVE_TOKEN__
# while the pod still ran an image that only knew POWERGRID_SIMU_UPSTREAM, and
# proxy_set_header replaced the real token the bundle was still sending with the
# literal string "__COGNITIVE_TOKEN__". Set ALLOW_MISSING_ENV=1 to push anyway.
# ---------------------------------------------------------------------------
echo "--- pre-flight: placeholders in the conf vs env on deploy/$DEPLOY"

placeholders=$(grep -o '__[A-Z_][A-Z_]*__' /tmp/nginx.conf.repo | sort -u || true)
if [ -z "$placeholders" ]; then
  echo "  (none)"
fi

env_names=$(kubectl -n "$NS" get "deploy/$DEPLOY" \
  -o go-template='{{range .spec.template.spec.containers}}{{range .env}}{{.name}}{{"\n"}}{{end}}{{end}}')

problems=""
for ph in $placeholders; do
  name=${ph#__}; name=${name%__}

  if ! printf '%s\n' "$env_names" | grep -qx "$name"; then
    problems="${problems}  ${name}: no env var of that name on deploy/${DEPLOY}"$'\n'
    echo "  $name: MISSING from the deployment"
    continue
  fi

  # Declared is not the same as resolvable: a secretKeyRef to a secret or key that does
  # not exist leaves the pod in CreateContainerConfigError, and the OLD pod keeps serving.
  ref=$(kubectl -n "$NS" get "deploy/$DEPLOY" -o go-template="{{range .spec.template.spec.containers}}{{range .env}}{{if eq .name \"${name}\"}}{{with .valueFrom}}{{with .secretKeyRef}}{{.name}}/{{.key}}{{end}}{{end}}{{end}}{{end}}{{end}}")

  if [ -n "$ref" ]; then
    sname=${ref%%/*}; skey=${ref##*/}
    if ! keys=$(kubectl -n "$NS" get secret "$sname" -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null); then
      problems="${problems}  ${name}: secretKeyRef -> secret '${sname}' does not exist in namespace ${NS}"$'\n'
      echo "  $name: <- secret $sname/$skey (SECRET NOT FOUND)"
    elif ! printf '%s\n' "$keys" | grep -qx "$skey"; then
      problems="${problems}  ${name}: secret '${sname}' exists but has no key '${skey}' (keys: $(printf '%s ' $keys))"$'\n'
      echo "  $name: <- secret $sname/$skey (KEY NOT FOUND)"
    else
      echo "  $name: <- secret $sname/$skey (ok)"
    fi
    continue
  fi

  # A literal value. Never echo one that is named like a credential.
  val=$(kubectl -n "$NS" get "deploy/$DEPLOY" -o go-template="{{range .spec.template.spec.containers}}{{range .env}}{{if eq .name \"${name}\"}}{{.value}}{{end}}{{end}}{{end}}")
  case "$name" in
    *TOKEN*|*SECRET*|*PASSWORD*) echo "  $name: set inline (${#val} chars)" ;;
    *)                           echo "  $name: $val" ;;
  esac
done

if [ -n "$problems" ]; then
  echo >&2
  echo "REFUSING to push: the conf carries placeholders this deployment cannot substitute." >&2
  printf '%s' "$problems" >&2
  echo "Fix the deployment first (add the env var, or create the secret/key), then re-run." >&2
  echo "Pushing now would leave nginx serving a silently broken proxy - it starts fine and" >&2
  echo "the failure only shows up as a 401 from the upstream." >&2
  if [ "${ALLOW_MISSING_ENV:-0}" != "1" ]; then
    echo "Override with ALLOW_MISSING_ENV=1 if you really mean to." >&2
    exit 1
  fi
  echo "ALLOW_MISSING_ENV=1 - continuing anyway." >&2
fi

echo
read -r -p "Apply to $NS/$CM and restart $DEPLOY? [y/N] " ans
case "$ans" in
  y|Y|yes|YES|Yes) ;;
  *) echo "ABORTED - nothing was applied."; exit 0 ;;
esac

kubectl -n "$NS" patch cm "$CM" --type merge -p "$PATCH"
kubectl -n "$NS" rollout restart "deploy/$DEPLOY"
kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=180s

# ---------------------------------------------------------------------------
# Verify against the config nginx ACTUALLY loaded.
#
# start-webui.sh runs `nginx -c /personal-conf/nginx.conf`, and that tree is built at
# startup from the ConfigMap with the placeholders substituted. A bare `nginx -T` ignores
# it and re-reads the default /etc/nginx/nginx.conf, which pulls in the raw ConfigMap
# mount - where `proxy_pass __POWERGRID_SIMU_UPSTREAM__;` is not a valid URL. nginx then
# exits non-zero and prints no dump at all, which reads as "the location is missing".
# That false negative is why this script reported FAILED on a healthy pod.
# ---------------------------------------------------------------------------
NGINX_CONF=/personal-conf/nginx.conf

# Target one Running pod, not deploy/... : during a rollout that can select the pod being
# terminated and report on the config we just replaced.
SELECTOR=$(kubectl -n "$NS" get "deploy/$DEPLOY" \
  -o go-template='{{range $k,$v := .spec.selector.matchLabels}}{{$k}}={{$v}},{{end}}' | sed 's/,$//')
POD=$(kubectl -n "$NS" get pods -l "$SELECTOR" --field-selector=status.phase=Running \
  --sort-by=.metadata.creationTimestamp -o name | tail -1)

if [ -z "$POD" ]; then
  echo "FAILED - no Running pod matching '$SELECTOR' in namespace $NS." >&2
  kubectl -n "$NS" get pods -l "$SELECTOR" >&2
  exit 1
fi
echo "--- verify: the config loaded by $POD ($NGINX_CONF)"

# Keep stderr: if nginx rejects the config, its reason is the whole point.
if ! dump=$(kubectl -n "$NS" exec "$POD" -- nginx -T -c "$NGINX_CONF" 2>&1); then
  echo "FAILED - nginx could not dump $NGINX_CONF in $POD:" >&2
  printf '%s\n' "$dump" >&2
  exit 1
fi

rc=0

for loc in /powergrid-simu/ /cognitive-api/; do
  if printf '%s\n' "$dump" | grep -q "location $loc"; then
    echo "OK   - location $loc is live."
  else
    echo "FAIL - location $loc is NOT in the running config." >&2
    rc=1
  fi
done

# The failure this script exists to catch: a placeholder that reached the running config
# unsubstituted. It means the image predates the variable, or the env var never arrived.
leftover=$(printf '%s\n' "$dump" | grep -o '__[A-Z_][A-Z_]*__' | sort -u || true)
if [ -n "$leftover" ]; then
  echo "FAIL - unsubstituted placeholders in the RUNNING config:" >&2
  printf '  %s\n' $leftover >&2
  echo "  The pod's image cannot substitute these. Check that its start-webui.sh lists them" >&2
  echo "  in SUBST_VARS - an image older than the conf is the usual cause:" >&2
  kubectl -n "$NS" get "$POD" -o jsonpath='{.spec.containers[*].image}{"\n"}' >&2
  rc=1
else
  echo "OK   - no unsubstituted placeholders in the running config."
fi

# Never print the dump itself - it now carries the substituted token.
echo "--- /cognitive-api/ as loaded (token redacted):"
printf '%s\n' "$dump" | grep -A8 'location /cognitive-api/' |
  sed -E 's/(Authorization "Bearer )[^"]*/\1<redacted>/'

if [ "$rc" -ne 0 ]; then
  echo >&2
  echo "  ConfigMap occurrences of powergrid-simu in the cluster:" >&2
  kubectl -n "$NS" get cm "$CM" -o jsonpath='{.data.nginx\.conf}' | grep -c powergrid-simu >&2 || true
  echo "  (0 above = the patch did not stick, e.g. ArgoCD self-heal reverted it)" >&2
  echo "  Pods (a crashlooping new pod leaves the OLD one serving):" >&2
  kubectl -n "$NS" get pods -l "$SELECTOR" >&2
  exit 1
fi

echo "--- all checks passed."
