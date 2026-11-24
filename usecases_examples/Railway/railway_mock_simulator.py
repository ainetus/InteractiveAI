"""Mock Railway simulator for testing the InteractiveAI Railway use case.

No Railway simulator ships with this repository, so this script plays its part:

  publish  Logs in as the simulator account, posts a context (10 TGVs on the
           Paris - Bordeaux high-speed line) and 10 events, one per train. Their
           `id_event` ("1" to "10") are the keys of the Railway recommendation catalog
           (backend/recommendation-service/resources/Railway/mockRecommendations).
  serve    Listens for the recommendation the operator applies
           (POST <VITE_RAILWAY_SIMU>/transport_plan) and prints it, and
           republishes the context every 10 s like a running simulator.
           For human experiments, a UI built with VITE_RAILWAY_SESSION_EVENTS=true
           posts <VITE_RAILWAY_SIMU>/experiment/start when it gets its first
           context of a session: the 10 events are then published, once per
           session, in the language the UI sends ("en" or "fr"). (A real
           simulator publishes its incidents on its own; the UI only calls this
           endpoint in experiment builds.)

The UI only takes a context published after the operator logged in (an older
one is treated as stale), and asks for no recommendation without a context:
`serve` keeps a fresh one coming, so an operator who logs in gets one within
about 15 s.

Standard library only. Examples:

  python3 railway_mock_simulator.py serve
  python3 railway_mock_simulator.py serve --context-every 0      # receiver only
  python3 railway_mock_simulator.py publish                      # context + events
  python3 railway_mock_simulator.py publish --only 2
  python3 railway_mock_simulator.py publish --lang fr                # events in French
  python3 railway_mock_simulator.py publish --context-only
"""
import argparse
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Stations of the Paris - Bordeaux line (latitude, longitude)
STATIONS = {
    "Paris Montparnasse": (48.8412, 2.3203),
    "St Pierre des Corps": (47.3857, 0.7231),
    "Chatellerault": (46.8178, 0.5466),
    "Poitiers": (46.5823, 0.3333),
    "Angouleme": (45.6535, 0.1650),
    "Bordeaux St Jean": (44.8256, -0.5562),
}

TRAINS = [
    # id_train, position, passengers, speed (km/h), failure
    ("TGV 8501", (47.40, 0.74), 468, 0, True),
    ("TGV 8515", (46.60, 0.35), 398, 0, False),
    ("TGV 8533", (44.86, -0.52), 512, 40, True),
    ("TGV 8541", (46.66, 0.40), 455, 0, False),
    ("TGV 8507", (46.90, 0.58), 380, 0, False),
    ("TGV 8547", (46.10, 0.25), 502, 160, False),
    ("TGV 8555", (47.55, 0.90), 430, 0, True),
    ("TGV 8521", (46.583, 0.334), 289, 0, True),
    ("TGV 8537", (44.88, -0.49), 520, 0, False),
    ("TGV 8561", (45.70, 0.18), 410, 220, False),
]

# One event per catalog entry, each on its own train. The titles match what the
# catalog proposes for each one; criticalities and types vary so that the
# operator has to prioritise.
EVENTS = [
    {
        "id_event": "1",
        "title": "Catenary failure near St Pierre des Corps",
        "description": "Traction power lost on track 1; TGV 8501 stopped before the station.",
        "fr": {
            "title": "Panne de caténaire près de St Pierre des Corps",
            "description": "Perte d'alimentation de traction sur la voie 1 ; le TGV 8501 est arrêté avant la gare.",
        },
        "criticality": "HIGH",
        "event_type": "INFRASTRUCTURE",
        "id_train": "TGV 8501",
        "delay": 90,
        "route": ["Paris Montparnasse", "St Pierre des Corps", "Poitiers", "Bordeaux St Jean"],
    },
    {
        "id_event": "2",
        "title": "Passenger taken ill on board",
        "description": "Medical assistance requested on TGV 8515 near Poitiers.",
        "fr": {
            "title": "Malaise d'un voyageur à bord",
            "description": "Assistance médicale demandée à bord du TGV 8515 près de Poitiers.",
        },
        "criticality": "MEDIUM",
        "event_type": "PASSENGER",
        "id_train": "TGV 8515",
        "delay": 30,
        "route": ["Paris Montparnasse", "Poitiers", "Angouleme", "Bordeaux St Jean"],
    },
    {
        "id_event": "3",
        "title": "Rolling stock failure approaching Bordeaux",
        "description": "Brake fault reported by TGV 8533; speed limited to 40 km/h.",
        "fr": {
            "title": "Panne de matériel à l'approche de Bordeaux",
            "description": "Défaut de freinage signalé par le TGV 8533 ; vitesse limitée à 40 km/h.",
        },
        "criticality": "HIGH",
        "event_type": "HARDWARE",
        "id_train": "TGV 8533",
        "delay": 60,
        "route": ["Paris Montparnasse", "Angouleme", "Bordeaux St Jean"],
    },
    {
        "id_event": "4",
        "title": "Signalling failure near Poitiers",
        "description": "Signals out of order over 12 km north of Poitiers; TGV 8541 stopped at a red signal.",
        "fr": {
            "title": "Panne de signalisation près de Poitiers",
            "description": "Signaux hors service sur 12 km au nord de Poitiers ; le TGV 8541 est arrêté à un signal fermé.",
        },
        "criticality": "HIGH",
        "event_type": "INFRASTRUCTURE",
        "id_train": "TGV 8541",
        "delay": 45,
        "route": ["Paris Montparnasse", "St Pierre des Corps", "Poitiers", "Angouleme", "Bordeaux St Jean"],
    },
    {
        "id_event": "5",
        "title": "Fallen tree on the track near Chatellerault",
        "description": "A tree blown down by the wind blocks track 1; TGV 8507 stopped before it.",
        "fr": {
            "title": "Arbre tombé sur la voie près de Châtellerault",
            "description": "Un arbre abattu par le vent obstrue la voie 1 ; le TGV 8507 est arrêté devant.",
        },
        "criticality": "MEDIUM",
        "event_type": "INFRASTRUCTURE",
        "id_train": "TGV 8507",
        "delay": 35,
        "route": ["Paris Montparnasse", "Chatellerault", "Poitiers", "Bordeaux St Jean"],
    },
    {
        "id_event": "6",
        "title": "Heat-related speed restriction near Angouleme",
        "description": "Track temperature above 50 °C: speed limited to 160 km/h over 20 km for TGV 8547.",
        "fr": {
            "title": "Limitation de vitesse due à la chaleur près d'Angoulême",
            "description": "Température du rail supérieure à 50 °C : vitesse limitée à 160 km/h sur 20 km pour le TGV 8547.",
        },
        "criticality": "LOW",
        "event_type": "INFRASTRUCTURE",
        "id_train": "TGV 8547",
        "delay": 15,
        "route": ["Paris Montparnasse", "Poitiers", "Angouleme", "Bordeaux St Jean"],
    },
    {
        "id_event": "7",
        "title": "Pantograph damage, train stranded near Tours",
        "description": "TGV 8555 lost its pantograph and traction power; it cannot move on its own.",
        "fr": {
            "title": "Pantographe endommagé, train immobilisé près de Tours",
            "description": "Le TGV 8555 a perdu son pantographe et sa traction ; il ne peut plus avancer seul.",
        },
        "criticality": "HIGH",
        "event_type": "HARDWARE",
        "id_train": "TGV 8555",
        "delay": 120,
        "route": ["Paris Montparnasse", "St Pierre des Corps", "Poitiers", "Bordeaux St Jean"],
    },
    {
        "id_event": "8",
        "title": "Door fault at Poitiers station",
        "description": "A door of coach 4 of TGV 8521 does not close; departure blocked.",
        "fr": {
            "title": "Porte bloquée en gare de Poitiers",
            "description": "Une porte de la voiture 4 du TGV 8521 ne se ferme pas ; départ impossible.",
        },
        "criticality": "LOW",
        "event_type": "HARDWARE",
        "id_train": "TGV 8521",
        "delay": 10,
        "route": ["Paris Montparnasse", "Poitiers", "Angouleme", "Bordeaux St Jean"],
    },
    {
        "id_event": "9",
        "title": "Unattended baggage at Bordeaux St Jean",
        "description": "Security perimeter set up around platforms 1 to 3; TGV 8537 cannot enter the station.",
        "fr": {
            "title": "Bagage abandonné à Bordeaux St Jean",
            "description": "Périmètre de sécurité autour des voies 1 à 3 ; le TGV 8537 ne peut pas entrer en gare.",
        },
        "criticality": "MEDIUM",
        "event_type": "PASSENGER",
        "id_train": "TGV 8537",
        "delay": 40,
        "route": ["Paris Montparnasse", "Poitiers", "Angouleme", "Bordeaux St Jean"],
    },
    {
        "id_event": "10",
        "title": "Delay threatening connections at Bordeaux",
        "description": "TGV 8561 runs 25 min late; 180 passengers risk missing their regional connections.",
        "fr": {
            "title": "Retard menaçant les correspondances à Bordeaux",
            "description": "Le TGV 8561 circule avec 25 min de retard ; 180 voyageurs risquent de manquer leur correspondance régionale.",
        },
        "criticality": "MEDIUM",
        "event_type": "IMPACT",
        "id_train": "TGV 8561",
        "delay": 25,
        "route": ["Paris Montparnasse", "Poitiers", "Angouleme", "Bordeaux St Jean"],
    },
]


def request(method, url, body=None, token=None, form=False):
    headers = {}
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        raise SystemExit(f"{method} {url} -> {err.code}: {err.read().decode(errors='replace')[:500]}")


def login(base, username, password):
    answer = request(
        "POST",
        f"{base}/auth/token",
        {"username": username, "password": password, "grant_type": "password", "clientId": "opfab-client"},
        form=True,
    )
    return answer["access_token"]


def travel_plan(route, delay_min):
    """Stops of the train, in epoch milliseconds, as the Timeline expects."""
    start = datetime.now(timezone.utc)
    plan = []
    for i, name in enumerate(route):
        arrival = start + timedelta(minutes=45 * i + (delay_min if i else 0))
        plan.append({
            "name": name,
            "startDate": int(arrival.timestamp() * 1000),
            "endDate": int((arrival + timedelta(minutes=3)).timestamp() * 1000),
        })
    return plan


def post_context(url, token):
    """Posts the trains' context; each post is a new context for the UI."""
    context = {
        "use_case": "Railway",
        "date": datetime.now(timezone.utc).isoformat(),
        "data": {
            "trains": [
                {
                    "id_train": id_train,
                    "latitude": lat,
                    "longitude": lng,
                    "nb_passengers_onboard": passengers,
                    "nb_passengers_connection": None,
                    "speed": speed,
                    "failure": failure,
                }
                for id_train, (lat, lng), passengers, speed, failure in TRAINS
            ],
            "list_of_target": {},
            "direction_agents": [],
            "position_agents": {},
        },
    }
    request("POST", f"{url}/cabcontext/api/v1/contexts", context, token)


def publish(args):
    token = login(args.url, args.user, args.password)
    post_context(args.url, token)
    print(f"context: {len(TRAINS)} trains")
    if not args.context_only:
        publish_events(args.url, token, args.only, args.lang)


def publish_events(url, token, only=None, lang="en"):
    """Posts the events (all of them, or those whose id_event is in `only`), in English or French."""
    now = datetime.now(timezone.utc)
    positions = {t[0]: t[1] for t in TRAINS}
    for event in EVENTS:
        if only and event["id_event"] not in only:
            continue
        lat, lng = positions[event["id_train"]]
        texts = event["fr"] if lang == "fr" else event
        payload = {
            "use_case": "Railway",
            "title": texts["title"],
            "description": texts["description"],
            "criticality": event["criticality"],
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(hours=2)).isoformat(),
            "data": {
                "id_event": event["id_event"],
                "event_type": event["event_type"],
                "agent_id": event["id_train"],
                "id_train": event["id_train"],
                "delay": event["delay"],
                "agent_position": None,
                "malfunction_stop_position": None,
                "travel_plan": travel_plan(event["route"], event["delay"]),
                "latitude": lat,
                "longitude": lng,
                "simulation_name": "railway-mock",
            },
        }
        request("POST", f"{url}/cab_event/api/v1/events", payload, token)
        print(f"event {event['id_event']}: {event['criticality']:6s} {texts['title']}", flush=True)


class TransportPlanHandler(BaseHTTPRequestHandler):
    """Receives what the UI sends: the applied recommendation, and the start of
    an operator's session. Sends CORS headers: the browser posts here directly."""

    # Set by serve(): the platform to publish to, and the sessions already given their events
    args = None
    sessions = set()
    sessions_lock = threading.Lock()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        path = self.path.rstrip("/")
        if path not in ("/transport_plan", "/experiment/start"):
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if path == "/experiment/start":
            lang = "fr" if body.get("lang") == "fr" else "en"
            answer = self._start_session(str(body.get("session_id") or ""), lang)
        else:
            print(time.strftime("%H:%M:%S"), "applied recommendation:", json.dumps(body, ensure_ascii=False), flush=True)
            answer = {"message": "Transport plan received by the mock simulator"}
        self._reply(answer)

    def _start_session(self, session_id, lang="en"):
        """Publishes the events once per operator session, when its UI gets its first context,
        in the operator's language."""
        if not session_id:
            return {"message": "session_id missing", "published": False}
        with self.sessions_lock:
            if session_id in self.sessions:
                return {"message": "Events already published for this session", "published": False}
            self.sessions.add(session_id)
        print(time.strftime("%H:%M:%S"), f"session {session_id}: publishing the events ({lang})", flush=True)
        threading.Thread(target=self._publish_events, args=(session_id, lang), daemon=True).start()
        return {"message": "Events published for this session", "published": True}

    def _publish_events(self, session_id, lang):
        args = self.args
        try:
            publish_events(args.url, login(args.url, args.user, args.password), lang=lang)
        except (Exception, SystemExit) as err:  # request() exits on HTTP errors
            # Let the UI try again with its next context
            with self.sessions_lock:
                self.sessions.discard(session_id)
            print(time.strftime("%H:%M:%S"), f"session {session_id}: cannot publish the events ({err})", flush=True)

    def _reply(self, payload):
        answer = json.dumps(payload).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    def log_message(self, *_):
        pass


def republish_context(args):
    """Posts the context every `context_every` seconds, as a running simulator would.

    The UI ignores a context that already existed when the operator logged in,
    so a fresh one has to keep coming. Logs in again each time: tokens expire,
    and the platform may restart in between.
    """
    failing = False
    while True:
        try:
            post_context(args.url, login(args.url, args.user, args.password))
            if failing:
                print(time.strftime("%H:%M:%S"), "context: publishing again", flush=True)
            failing = False
        except (Exception, SystemExit) as err:  # request() exits on HTTP errors
            if not failing:
                print(time.strftime("%H:%M:%S"), f"context: cannot publish ({err}), retrying", flush=True)
            failing = True
        time.sleep(args.context_every)


def serve(args):
    TransportPlanHandler.args = args
    if args.context_every > 0:
        threading.Thread(target=republish_context, args=(args,), daemon=True).start()
        print(f"Publishing the context to {args.url} every {args.context_every} s", flush=True)
    print(f"Listening on http://0.0.0.0:{args.port}/transport_plan", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), TransportPlanHandler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    pub = sub.add_parser("publish", help="post the context and the events")
    pub.add_argument("--url", default="http://localhost:3200", help="InteractiveAI frontend URL")
    pub.add_argument("--user", default="publisher_test")
    pub.add_argument("--password", default="test")
    pub.add_argument("--only", nargs="*", help="id_event to publish (1 to 10); all by default")
    pub.add_argument("--lang", choices=("en", "fr"), default="en", help="language of the events; en by default")
    pub.add_argument(
        "--context-only",
        action="store_true",
        help="post only the context; the UI ignores a context published before the operator "
        "logged in, so re-run this after logging in",
    )
    pub.set_defaults(func=publish)

    srv = sub.add_parser("serve", help="receive applied recommendations and keep the context fresh")
    srv.add_argument("--port", type=int, default=5124)
    srv.add_argument("--url", default="http://localhost:3200", help="InteractiveAI frontend URL")
    srv.add_argument("--user", default="publisher_test")
    srv.add_argument("--password", default="test")
    srv.add_argument(
        "--context-every",
        type=float,
        default=10,
        help="seconds between two context posts (0: never); 10 by default",
    )
    srv.set_defaults(func=serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
