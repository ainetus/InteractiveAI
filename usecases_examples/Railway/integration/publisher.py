"""
Publisher: sends the simulator's events and contexts to InteractiveAI (D1-D3, D7).

Only the platform's interoperability APIs, never OperatorFabric: events to
POST /cab_event/api/v1/events, contexts to POST /cabcontext/api/v1/contexts. One token per
session, as publisher_test (POST /auth/token), reused until it expires or a request gets a 401.

Settings (environment, see from_env()):
    RAILWAY_PLATFORM_URL        the platform's URL as the browser sees it (default http://127.0.0.1:3200,
                                the dev gateway); the simulator reaches the services through its nginx
    RAILWAY_PUBLISHER_USER      default publisher_test
    RAILWAY_PUBLISHER_PASSWORD  default test
"""

import logging
import os
import time
from typing import Callable, Optional

import requests

log = logging.getLogger(__name__)

EVENTS_PATH = "/cab_event/api/v1/events"
CONTEXTS_PATH = "/cabcontext/api/v1/contexts"
TOKEN_PATH = "/auth/token"
REFRESH_MARGIN_S = 30      # renew the token this long before it expires
TIMEOUT_S = 10


class Publisher:
    def __init__(self, base_url: str, user: str, password: str,
                 http: Optional[requests.Session] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.http = http or requests.Session()
        self.clock = clock
        self._authorization: Optional[str] = None
        self._expires_at = 0.0

    @classmethod
    def from_env(cls) -> "Publisher":
        return cls(os.getenv("RAILWAY_PLATFORM_URL", "http://127.0.0.1:3200"),
                   os.getenv("RAILWAY_PUBLISHER_USER", "publisher_test"),
                   os.getenv("RAILWAY_PUBLISHER_PASSWORD", "test"))

    def send_event(self, payload: dict) -> Optional[dict]:
        return self._post(EVENTS_PATH, payload)

    def send_context(self, payload: dict) -> Optional[dict]:
        return self._post(CONTEXTS_PATH, payload)

    # ── internals ─────────────────────────────────────────────────────────

    def _login(self):
        response = self.http.post(self.base_url + TOKEN_PATH, data={
            "username": self.user, "password": self.password,
            "grant_type": "password", "clientId": "opfab-client",
        }, timeout=TIMEOUT_S)
        response.raise_for_status()
        token = response.json()
        self._authorization = f"{token.get('token_type', 'Bearer')} {token['access_token']}"
        self._expires_at = self.clock() + float(token.get("expires_in", 300)) - REFRESH_MARGIN_S

    def _auth_header(self) -> dict:
        if self._authorization is None or self.clock() >= self._expires_at:
            self._login()
        return {"Authorization": self._authorization}

    def _post(self, path: str, payload: dict) -> Optional[dict]:
        url = self.base_url + path
        response = self.http.post(url, json=payload, headers=self._auth_header(), timeout=TIMEOUT_S)
        if response.status_code == 401:          # revoked or expired early: one new token, one retry
            self._authorization = None
            response = self.http.post(url, json=payload, headers=self._auth_header(), timeout=TIMEOUT_S)
        if not response.ok:
            log.error("POST %s failed with %s: %s", path, response.status_code, response.text[:500])
        response.raise_for_status()
        return response.json() if response.content else None
