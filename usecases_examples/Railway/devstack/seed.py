"""
Post one Railway event and one context in today's schema (main), through the dev gateway, as a
publisher does: a token as publisher_test, then POST /cab_event/ and POST /cabcontext/.

Usage: python seed.py [gateway URL, default http://localhost:3200]
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

GATEWAY = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3200"


def request(method, path, body=None, token=None, form=False):
    data, headers = None, {}
    if body is not None:
        data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if token:
        headers["Authorization"] = f"{token['token_type']} {token['access_token']}"
    req = urllib.request.Request(GATEWAY + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def login():
    return request("POST", "/auth/token", {"username": "publisher_test", "password": "test",
                                           "grant_type": "password", "clientId": "opfab-client"},
                   form=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def seed_event(token, title="Signalstörung"):
    return request("POST", "/cab_event/api/v1/events", {
        "use_case": "Railway",
        "criticality": "HIGH",
        "title": title,
        "description": "Seed event of the dev stack, in today's Railway schema.",
        "start_date": now(),
        "data": {"event_type": "INFRASTRUCTURE", "id_train": "AB001", "agent_id": "0",
                 "id_event": None, "delay": 15},
    }, token)


def seed_context(token):
    return request("POST", "/cabcontext/api/v1/contexts", {
        "use_case": "Railway",
        "date": now(),
        "data": {"trains": [{"id_train": "AB001", "nb_passengers_onboard": 468,
                             "latitude": 46.58, "longitude": 0.33, "failure": True}]},
    }, token)


if __name__ == "__main__":
    t = login()
    event = seed_event(t)
    seed_context(t)
    print(f"seeded event {event.get('id_event', event)} and one context via {GATEWAY}")
