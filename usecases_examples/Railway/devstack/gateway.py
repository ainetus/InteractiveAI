"""
Dev gateway: the platform's single entry point on one machine, without Docker.

Stands in for the frontend nginx, Keycloak and OperatorFabric, so the real Event, Context, Historic
and Recommendation services can run on SQLite with AUTH_DISABLED=true:

- routes /cab_event/, /cabcontext/, /cab_recommendation/, /cabhistoric/ and /railway-simu/ to the
  locally started processes, stripping the prefix as nginx does;
- answers /auth/token with a fixed token per user ("devstack.<login>") and
  /users/CurrentUserWithPerimeters with that user and entities ["Railway"];
- keeps OperatorFabric's cards in memory: POST /cardspub/cards (the Event Service's
  CARDS_PUBLICATION_SERVICE), the /cards/cardSubscription stream, /cards/cards/<id>, deletes and
  acknowledgements;
- serves the frontend: FRONTEND=dist serves the built bundle (FRONTEND_DIST), FRONTEND=vite proxies
  to the Vite dev server (VITE_URL), its HMR websocket included.

Never expose it beyond localhost: it accepts any login. Standard library only.
"""

import http.client
import json
import mimetypes
import os
import queue
import select
import socket
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # repo root

PORT = int(os.getenv("GATEWAY_PORT", "3200"))
ROUTES = {
    "/cab_event/": os.getenv("EVENT_URL", "http://127.0.0.1:5000"),
    "/cabcontext/": os.getenv("CONTEXT_URL", "http://127.0.0.1:5100"),
    "/cabhistoric/": os.getenv("HISTORIC_URL", "http://127.0.0.1:5200"),
    "/cab_recommendation/": os.getenv("RECOMMENDATION_URL", "http://127.0.0.1:5400"),
    "/railway-simu/": os.getenv("RAILWAY_SIMU_URL", "http://127.0.0.1:5124"),
}
FRONTEND = os.getenv("FRONTEND", "dist")
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", ROOT / "frontend" / "dist"))
VITE_URL = os.getenv("VITE_URL", "http://127.0.0.1:5173")
ENTITIES = os.getenv("GATEWAY_ENTITIES", "Railway").split(",")
HEARTBEAT_S = 10

# ---------------------------------------------------------------- OperatorFabric stand-in

_cards = {}                       # card id -> card
_subscribers = set()              # one queue per open card stream
_lock = threading.Lock()


def _broadcast(event):
    line = "data:" + json.dumps(event)
    with _lock:
        for q in list(_subscribers):
            q.put(line)


def publish_card(payload):
    """Complete a card as OperatorFabric's cards-publication does and send it to the streams."""
    card_id = f"{payload['process']}.{payload['processInstanceId']}"
    now = int(time.time() * 1000)
    with _lock:
        old = _cards.get(card_id)
    card = {
        **payload,
        "id": card_id,
        "uid": str(uuid.uuid4()),
        "publishDate": now,
        "publisherType": "EXTERNAL",
        "processStateKey": f"{payload['process']}.{payload.get('state', '')}",
        "titleTranslated": payload.get("title", {}).get("parameters", {}).get("title", ""),
        "summaryTranslated": payload.get("summary", {}).get("parameters", {}).get("summary", ""),
        "keepChildCards": payload.get("keepChildCards", False),
        "hasBeenAcknowledged": False,
        "hasBeenRead": False,
    }
    with _lock:
        _cards[card_id] = card
    _broadcast({"type": "UPDATE" if old else "ADD",
                "entityRecipientsIds": card.get("entityRecipients", []), "card": card})
    return card


def delete_card(card_id):
    with _lock:
        card = _cards.pop(card_id, None)
    if card:
        _broadcast({"type": "DELETE", "cardId": card_id,
                    "entityRecipientsIds": card.get("entityRecipients", [])})
    return card


def acknowledge_card(uid, entities):
    with _lock:
        card = next((c for c in _cards.values() if c["uid"] == uid), None)
        if card:
            card["hasBeenAcknowledged"] = True
    if card:
        _broadcast({"type": "ACK", "cardUid": uid, "cardId": card["id"], "entitiesAcks": entities})
    return card


def _token(login):
    return {
        "access_token": f"devstack.{login}",
        "refresh_token": f"devstack.{login}",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_expires_in": 36000,
        "not-before-policy": 0,
        "session_state": "devstack",
        "scope": "openid",
    }


def _user(login):
    return {
        "userData": {"login": login, "firstName": login, "lastName": None, "entities": ENTITIES,
                     "authorizedIPAddresses": [], "groups": ["Dispatcher"]},
        "computedPerimeters": [{"process": "cabProcess", "state": "messageState",
                                "rights": "ReceiveAndWrite", "filteringNotificationAllowed": True}],
        "processesStatesNotNotified": {},
    }


# ---------------------------------------------------------------- HTTP


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.getenv("GATEWAY_LOG"):
            super().log_message(fmt, *args)

    # -- helpers

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _send(self, status, body=b"", ctype="application/json", headers=None):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _login(self):
        auth = self.headers.get("Authorization", "")
        token = auth.split(" ", 1)[1] if " " in auth else ""
        return token.split(".", 1)[1] if token.startswith("devstack.") else "railway_user"

    def _proxy(self, base, path):
        url = urllib.parse.urlsplit(base)
        conn = http.client.HTTPConnection(url.hostname, url.port, timeout=60)
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "connection", "accept-encoding")}
        try:
            conn.request(self.command, path, body=self._body() or None, headers=headers)
            resp = conn.getresponse()
            body = resp.read()
        except OSError as e:
            return self._send(502, {"error": f"{base} unreachable: {e}"})
        finally:
            conn.close()
        skip = ("transfer-encoding", "connection", "content-length", "content-encoding")
        self._send(resp.status, body, resp.getheader("Content-Type", "application/octet-stream"),
                   {k: v for k, v in resp.getheaders() if k.lower() not in skip and k.lower() != "content-type"})

    # -- OperatorFabric and Keycloak stand-ins

    def _stream_cards(self, replay):
        """replay: send the stored cards first (OperatorFabric does it for the range subscription,
        not for the notification one)."""
        q = queue.Queue()
        with _lock:
            _subscribers.add(q)
            snapshot = list(_cards.values()) if replay else []
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        # no-transform: proxies that compress (Cypress) would otherwise hold the events back
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Transfer-Encoding", "chunked")   # as OperatorFabric: proxies pass it on
        self.send_header("X-Content-Type-Options", "nosniff")   # else browsers hold 1 KB back
        self.end_headers()
        self.close_connection = True

        def write(line):
            chunk = (line + "\n\n").encode()
            self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            self.wfile.flush()

        try:
            write("data:INIT")
            for card in snapshot:
                write("data:" + json.dumps({"type": "ADD", "card": card,
                                            "entityRecipientsIds": card.get("entityRecipients", [])}))
            while True:
                try:
                    write(q.get(timeout=HEARTBEAT_S))
                except queue.Empty:
                    write("data:HEARTBEAT")
        except OSError:
            pass
        finally:
            with _lock:
                _subscribers.discard(q)

    def _local(self, path):
        """Answer the Keycloak and OperatorFabric routes; False if the path is not one of them."""
        m = self.command
        if path == "/auth/token" and m == "POST":
            form = urllib.parse.parse_qs(self._body().decode())
            login = form.get("username", [""])[0]
            if not login and form.get("refresh_token", [""])[0].startswith("devstack."):
                login = form["refresh_token"][0].split(".", 1)[1]
            return self._send(200, _token(login or "railway_user")) or True
        if path == "/auth/check_token" and m == "POST":
            return self._send(200, {"active": True}) or True
        if path == "/users/CurrentUserWithPerimeters":
            return self._send(200, _user(self._login())) or True
        if path.startswith("/users/"):
            return self._send(200, {}) or True
        if path == "/cards/cardSubscription":
            self._body()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            return self._stream_cards(replay=query.get("notification") != ["true"]) or True
        if path == "/cards/willNewSubscriptionDisconnectAnExistingSubscription":
            return self._send(200, False) or True
        if path.startswith("/cards/cards/"):
            with _lock:
                card = _cards.get(path.rsplit("/", 1)[1])
            return self._send(200 if card else 404, {"card": card} if card else {}) or True
        if path == "/cardspub/cards" and m == "POST":
            card = publish_card(json.loads(self._body() or b"{}"))
            return self._send(201, {"id": card["id"], "uid": card["uid"]}) or True
        if path.startswith("/cardspub/cards/userAcknowledgement/") and m == "POST":
            entities = json.loads(self._body() or b"[]")
            card = acknowledge_card(path.rsplit("/", 1)[1], entities)
            return self._send(201 if card else 404, b"") or True
        if path.startswith("/cardspub/cards/") and m == "DELETE":
            card = delete_card(path.rsplit("/", 1)[1])
            return self._send(200 if card else 404, b"") or True
        if path.startswith("/cab_capitalization/") or path.startswith("/cognitive-api/"):
            # not started in the dev stack; answer like an empty service
            self._body()
            return self._send(200, {}) or True
        return False

    # -- frontend

    def _static(self, path):
        if not FRONTEND_DIST.is_dir():
            return self._send(503, f"No built frontend at {FRONTEND_DIST}: build it, or use "
                                   f"FRONTEND=vite.\n".encode(), "text/plain")
        target = (FRONTEND_DIST / path.lstrip("/")).resolve()
        if FRONTEND_DIST.resolve() not in target.parents or not target.is_file():
            target = FRONTEND_DIST / "index.html"          # SPA fallback, as nginx try_files
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype)

    def _tunnel(self):
        """Websocket upgrade (Vite HMR): pass the bytes through both ways."""
        url = urllib.parse.urlsplit(VITE_URL)
        upstream = socket.create_connection((url.hostname, url.port))
        head = f"{self.command} {self.path} {self.request_version}\r\n"
        head += "".join(f"{k}: {v}\r\n" for k, v in self.headers.items()) + "\r\n"
        upstream.sendall(head.encode())
        client = self.connection
        self.close_connection = True
        try:
            while True:
                ready, _, _ = select.select([client, upstream], [], [], 60)
                for s in ready:
                    data = s.recv(65536)
                    if not data:
                        return
                    (upstream if s is client else client).sendall(data)
        except OSError:
            pass
        finally:
            upstream.close()

    # -- dispatch

    def _handle(self):
        path = urllib.parse.urlsplit(self.path).path
        if self._local(path):
            return
        for prefix, base in ROUTES.items():
            if path.startswith(prefix):
                rest = self.path[len(prefix) - 1:]
                return self._proxy(base, rest)
        if FRONTEND == "vite":
            if self.headers.get("Upgrade", "").lower() == "websocket":
                return self._tunnel()
            return self._proxy(VITE_URL, self.path)
        return self._static(path)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _handle


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"gateway on http://localhost:{PORT} (frontend: {FRONTEND})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
