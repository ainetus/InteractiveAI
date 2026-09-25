#!/bin/bash

# Copyright (c) 2018-2022, RTE (http://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of the OperatorFabric project.
 
: '
  If the resolver is not indicated in the nginx conf, there could be side-effects (url not reachable). To solve this we must indicate
  the IP address available in the /etc/resolv.conf file. Given that this address can change between containers, it must be indicated
  dynamically => this is the purpose of this file
  The nginx.conf file is moved from /etc/nginx to /personal-conf and the default.conf file is moved from /etc/nginx/conf.d to
  /personal-conf/conf.d. Then nginx is run by indicating as the config directory /personal-conf
  The container will be run by running this file
'

# All nameservers on ONE line: nginx's resolver takes several addresses, and a multi-line
# value would splice a newline into the sed expression below, which fails with
# "sed: unmatched '/'" and writes an EMPTY default.conf. nginx then starts with no server
# block at all and answers nothing - a silent outage. Hosts with two nameservers in
# /etc/resolv.conf are common enough to hit this.
export resolver=$(awk '/^[[:space:]]*nameserver/ { printf "%s ", $2 }' /etc/resolv.conf)
if [ -z "$resolver" ]; then
    echo "ERROR: no nameserver in /etc/resolv.conf - cannot build the nginx resolver line." >&2
    exit 1
fi
resolver_replace="resolver $resolver ipv6=off;"
resolver_replaced=".*resolver.*"
nginx_conf_path_default="/etc/nginx"
nginx_conf_path_personal="/personal-conf"
defaultconf_default="$nginx_conf_path_default/conf.d/default.conf"
defaultconf_personal="$nginx_conf_path_personal/conf.d/default.conf"

printenv | grep resolver
echo "resolver_replace: $resolver_replace"
echo "resolver_replaced: $resolver_replaced"
echo "nginx_conf_path_default: $nginx_conf_path_default"
echo "nginx_conf_path_personal: $nginx_conf_path_personal"
echo "defaultconf_default: ${defaultconf_default}"
echo "defaultconf_personal: ${defaultconf_personal}"

mkdir /personal-conf
mkdir /personal-conf/conf.d

if grep -qe "$resolver_replaced" $defaultconf_default
then
    sed "s/$resolver_replaced/$resolver_replace/" $defaultconf_default > $defaultconf_personal
else
    sed "1i $resolver_replace" $defaultconf_default > $defaultconf_personal
fi

echo "The resolver in the personal default.conf:"
grep -e "$resolver_replaced" $defaultconf_personal

# The sed above is the one step that can fail while leaving a valid-but-useless config
# behind (an empty file passes `nginx -t`), so check the result rather than the exit code.
if [ ! -s $defaultconf_personal ]; then
    echo "ERROR: $defaultconf_personal is empty - the resolver substitution failed." >&2
    exit 1
fi

cat $nginx_conf_path_default/nginx.conf > $nginx_conf_path_personal/nginx.conf
sed -i "s/$(echo $nginx_conf_path_default | sed 's/\//\\\//g')\/conf\.d/$(echo $nginx_conf_path_personal | sed 's/\//\\\//g')\/conf\.d/" $nginx_conf_path_personal/nginx.conf

echo "The conf.d path in the personal nginx.conf file:"
grep "conf.d" $nginx_conf_path_personal/nginx.conf

: '
  Runtime configuration of the nginx conf.
  Every environment-specific value lives in the conf as a __NAME__ placeholder and is
  substituted here from the matching env var. To add one: give it a default below, append
  its name to SUBST_VARS, and use __NAME__ in the conf. Nothing else needs to change.

  Placeholders (rather than one conf per environment) keep a single conf serving local dev,
  cab-standalone and k8s alike. Secrets belong here too, not in the frontend bundle: a
  VITE_* value is inlined into the public JS at build time, so it is readable by anyone
  loading the app and can only be rotated by rebuilding the image.

  NB: this script only substitutes into conf.d/default.conf. In k8s that file comes from the
  cab-assistant-platform-config ConfigMap mounted over /etc/nginx/conf.d, which overrides
  the default.conf baked into the image - so the placeholders must be present there too.
'

# Where nginx forwards /powergrid-simu/. Defaults to a simulator container on the host.
: "${POWERGRID_SIMU_UPSTREAM:=http://host.docker.internal:5122/}"
# Bearer token for the INESCTEC cognitive API, injected into the /cognitive-api/ proxy.
: "${COGNITIVE_TOKEN:=}"

SUBST_VARS="POWERGRID_SIMU_UPSTREAM COGNITIVE_TOKEN"

# Names that must carry a NON-EMPTY value, space- or comma-separated. An empty required
# variable aborts startup instead of quietly substituting nothing.
#
# Opt-in rather than "everything is required" because an absent value is not always wrong.
# Local dev runs the whole stack without a cognitive token and merely loses the cognitive
# panel, so demanding one there would block work on unrelated features. A public deployment
# is the opposite case: an empty token means nginx sends "Bearer " with nothing after it and
# every /cognitive-api/ call 401s while the pod reports itself healthy. So
# deploy-chart/values.ovh.yaml sets REQUIRED_VARS=COGNITIVE_TOKEN and the pod crashloops
# instead - which in k8s leaves the previous pod serving, and puts the reason in the logs.
: "${REQUIRED_VARS:=}"

missing_required=""

for name in $SUBST_VARS; do
    eval "value=\$$name"
    # Escape the sed replacement metacharacters, including the # delimiter, so tokens and
    # URLs containing them cannot break out of the expression.
    escaped=$(printf '%s' "$value" | sed -e 's/[\\&#]/\\&/g')
    sed -i "s#__${name}__#${escaped}#g" $defaultconf_personal
    # Secrets are not echoed; report only whether a value arrived.
    case "$name" in
        *TOKEN*|*SECRET*|*PASSWORD*)
            if [ -n "$value" ]; then echo "$name: set (${#value} chars)"; else echo "$name: EMPTY"; fi ;;
        *) echo "$name: $value" ;;
    esac
    # Collected rather than fatal on the spot, so the log names every missing variable in
    # one go instead of one per restart.
    if [ -z "$value" ] && printf '%s' "$REQUIRED_VARS" | tr ',' ' ' | grep -qw "$name"; then
        missing_required="$missing_required $name"
    fi
done

if [ -n "$missing_required" ]; then
    echo "ERROR: required runtime variable(s) empty:$missing_required" >&2
    echo "They are listed in REQUIRED_VARS=\"$REQUIRED_VARS\" and would have been substituted" >&2
    echo "into the nginx conf as empty strings - producing a proxy that answers requests but" >&2
    echo "sends no credentials, which surfaces only as a 401 from the upstream. Refusing to" >&2
    echo "start instead." >&2
    echo "In k8s: check the env var on the deployment, and that the secret and key it" >&2
    echo "references both exist (deploy-chart/apply-nginx-conf.sh reports this)." >&2
    exit 1
fi

# A placeholder that survives means its env var was never set. nginx would either refuse to
# start on an invalid proxy_pass or, worse, serve a silently broken proxy - so fail here,
# where the reason is obvious in the container logs.
leftover=$(grep -o '__[A-Z_][A-Z_]*__' $defaultconf_personal | sort -u)
if [ -n "$leftover" ]; then
    echo "ERROR: unsubstituted placeholders in $defaultconf_personal:" >&2
    echo "$leftover" >&2
    echo "Set the matching env vars, or add them to SUBST_VARS in start-webui.sh." >&2
    exit 1
fi

# Validate before handing over to the daemon, so a bad conf fails at startup with a message
# rather than at the first request.
if ! nginx -t -c $nginx_conf_path_personal/nginx.conf; then
    echo "ERROR: nginx rejected the generated configuration (see above)." >&2
    exit 1
fi

# `nginx -t` accepts a config with no server block, so it would not catch a conf.d file that
# got mangled into something empty or serverless. Check we will actually serve something.
if ! grep -q "listen" $defaultconf_personal; then
    echo "ERROR: no listen directive in $defaultconf_personal - nginx would start and serve" >&2
    echo "nothing. The file is $(wc -c < $defaultconf_personal) bytes; its locations are:" >&2
    # Never cat the file: it now carries the substituted secrets.
    grep -n "location" $defaultconf_personal >&2 || echo "  (none)" >&2
    exit 1
fi

/usr/sbin/crond

nginx -c /personal-conf/nginx.conf -g "daemon off;"
