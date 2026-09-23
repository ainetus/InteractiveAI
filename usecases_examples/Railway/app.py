"""
app.py - Flask brain for the Railway use case.

Endpoints:
    GET  /health     - is the brain alive?
    GET  /state      - current train positions + directions
    POST /control    - start / pause / resume / reset / speed
    GET  /conflicts  - current conflict + resolution options
    POST /resolve    - apply a chosen resolution option
    GET  /render     - PNG image of current Flatland state

MAP FILE: Set MAP_PATH below.
"""

import io
import threading
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from PIL import Image

from Corridor_environment import load_corridor_env
from ScenarioManager import ScenarioManager
from TimetableDispatcher import TimetableDispatcher
from ScenarioPlayer import ScenarioPlayer, ScenarioState
from SessionManager import SessionManager, _sessions
from experiment_scenarios import ALL_SCENARIOS
from ExperimentLogger import save_experiment_log, list_logs, read_log

MAP_PATH = "maps/4city_map.pkl"

CONTEXT_SERVICE_URL = "http://localhost:3200/cab_context/api/v1/contexts"
EVENT_SERVICE_URL   = "http://localhost:3200/cab_event/api/v1/events"
INTERACTIVEAI_TOKEN = ""
SNAPSHOT_INTERVAL_S = 3.0


def _get_auth_token():
    """Get a fresh token from Keycloak for pushing to InteractiveAI services."""
    try:
        response = requests.post(
            "http://localhost:3200/auth/token",
            data={
                "username":   "admin",
                "password":   "test",
                "grant_type": "password",
                "client_id":  "opfab-client",
            },
            timeout=5,
        )
        data = response.json()
        return data.get("access_token", "")
    except Exception as e:
        print("[auth] Failed to get token:", e)
        return ""

app = Flask(__name__)
CORS(app)

state_lock = threading.Lock()

# ── Static presentation event (shown from startup for demo purposes) ──────────
PRESENTATION_EVENT = {
    # Platform-compatible fields
    "event_type":  "INFRASTRUCTURE",
    "id_train":    "Train_0",
    "agent_id":    "0",
    "delay":       0,
    # Flatland-specific fields
    "train_b":     "Train_1",
    "cell":        [15, 12],
    "conflict_id": "demo_event_1",
    "message":     "Heavy snowfall on route City_1 to City_0",
}

PRESENTATION_OPTIONS = [
    {
        "index": 0,
        "train_to_delay": 0,
        "resolution_type": "reroute",
        "delay_added": 8,
        "description": "Reroute Train 0 via City_2 (+ 8 min delay)",
    },
    {
        "index": 1,
        "train_to_delay": 1,
        "resolution_type": "reroute",
        "delay_added": 6,
        "description": "Reroute Train 1 via City_0 bypass (+ 6 min delay)",
    },
    {
        "index": 2,
        "train_to_delay": 0,
        "resolution_type": "wait",
        "delay_added": 12,
        "description": "Hold Train 0 at City_1 station until track is cleared (+ 12 min delay)",
    },
]

sim = {
    "env":              None,
    "stations":         None,
    "junctions":        None,
    "manager":          None,
    "dispatcher":       None,
    "renderer":         None,
    "step":             0,
    "running":          False,
    "speed":            1.0,
    "active_conflict":  None,
    "options":          [],
    "conflict_pushed":  False,
    "history":          [],   # list of agent states per step, for ZWL diagram
}

# ── Scenario state ─────────────────────────────────────────────────────────────
# Active scenario player (None when in free-run mode)
scenario_player: ScenarioPlayer | None = None
session_manager = SessionManager()
# Current session mode: "recommendation" or "colearning"
session_mode: str = "recommendation"
# Train currently selected by user in CoLearning mode (for map highlight)
selected_train: str = ""
pushed_card_ids: list = []
pushed_process_instance_ids: list = []
preview_scenario_id: str = ""
# Last decision made — stored for experiment log export
last_decision: dict = {}


def _init_simulation():
    from flatland.utils.rendertools import RenderTool
    env, stations, junctions = load_corridor_env(MAP_PATH)
    manager = ScenarioManager(env, stations, junctions)
    timetable, train_infos, priorities = manager.load_scenario_manual(0)
    dispatcher = TimetableDispatcher(
        env, timetable,
        train_infos=train_infos,
        enable_random_delays=False,
    )
    renderer = RenderTool(env, gl="PILSVG", screen_width=600, screen_height=600)
    with state_lock:
        sim["env"]             = env
        sim["stations"]        = stations
        sim["junctions"]       = junctions
        sim["manager"]         = manager
        sim["dispatcher"]      = dispatcher
        sim["renderer"]        = renderer
        sim["step"]            = 0
        sim["running"]         = False
        sim["active_conflict"] = None
        sim["options"]         = []
        sim["conflict_pushed"] = False
        sim["history"]         = []


def _sim_loop():
    while True:
        with state_lock:
            running = sim["running"]
            speed   = sim["speed"]

        if not running:
            time.sleep(0.1)
            continue

        try:
            _advance_one_step()
        except Exception as e:
            import traceback
            print("[sim_loop] Step failed:")
            traceback.print_exc()
            with state_lock:
                sim["running"] = False

        time.sleep(1.0 / max(speed, 0.1))


def _advance_one_step():
    with state_lock:
        env        = sim["env"]
        dispatcher = sim["dispatcher"]
        step       = sim["step"]

    actions = dispatcher.get_actions(step)

    # Hold Train 3 from step 15 to 29 (inclusive) in free-run mode
    DO_NOTHING = 4
    if 15 <= step <= 29:
        for agent in env.agents:
            if agent.handle == 3:
                actions[agent.handle] = DO_NOTHING

    # Train 2 is out of service in free-run mode (would create unwanted conflicts)
    for agent in env.agents:
        if agent.handle == 2:
            actions[agent.handle] = DO_NOTHING

    env.step(actions)

    new_step = step + 1
    with state_lock:
        sim["step"] = new_step

    # Record agent states for ZWL history
    with state_lock:
        env_ref = sim["env"]
        if env_ref is not None:
            step_record = {}
            for agent in env_ref.agents:
                step_record[str(agent.handle)] = {
                    "position": (
                        None if agent.position is None
                        else [int(c) for c in agent.position]
                    ),
                    "direction": int(agent.direction) if agent.direction is not None else 0,
                    "moving":    bool(agent.moving) if hasattr(agent, "moving") else False,
                    "target":    [int(c) for c in agent.target] if agent.target is not None else None,
                    "malfunction": 0,
                }
            sim["history"].append(step_record)

    # Check for conflicts every 5 steps to avoid slowing the loop
    if new_step % 5 == 0:
        _check_for_conflict()


def _check_for_conflict():
    with state_lock:
        manager           = sim["manager"]
        previous_conflict = sim["active_conflict"]

    try:
        conflict, options = manager.get_next_conflict_and_options()
    except AttributeError:
        return  # ScenarioManager doesn't support conflict detection
    except Exception as e:
        print("[conflict] Detection failed:", e)
        return

    with state_lock:
        sim["active_conflict"] = conflict
        sim["options"]         = options

        if conflict is not None:
            new_conflict = (
                previous_conflict is None
                or previous_conflict.train_a != conflict.train_a
                or previous_conflict.train_b != conflict.train_b
                or previous_conflict.cell    != conflict.cell
            )
            if new_conflict and not sim["conflict_pushed"]:
                sim["conflict_pushed"] = True
                threading.Thread(
                    target=_push_event,
                    args=(conflict,),
                    daemon=True,
                ).start()
        else:
            sim["conflict_pushed"] = False

def _snapshot_loop():
    while True:
        time.sleep(SNAPSHOT_INTERVAL_S)
        try:
            _push_snapshot()
        except Exception as e:
            print("[snapshot_loop] Failed:", e)


def _push_snapshot():
    with state_lock:
        env = sim["env"]
        if env is None:
            return
        position_agents  = {}
        direction_agents = []
        trains           = []
        for i, agent in enumerate(env.agents):
            pos = [int(x) for x in agent.position] if agent.position is not None else None
            direction = int(agent.direction) if agent.direction is not None else 0
            direction_agents.append(direction)
            position_agents[str(i)] = pos
            trains.append({
                "id_train":             "Train_" + str(i),
                "train_type":           "PASSENGER",
                "nb_passengers_onboard": 0,
                "position":             pos,
                "direction":            direction,
                "failure":              False,
                "speed":                1,
            })

    payload = {
        "use_case": "Railway",
        "date":     datetime.now(timezone.utc).isoformat(),
        "data": {
            "trains":           trains,
            "position_agents":  position_agents,
            "direction_agents": direction_agents,
        }
    }
    token = _get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        requests.post(CONTEXT_SERVICE_URL, json=payload, headers=headers, timeout=5)
    except Exception as e:
        print("[push_snapshot] Failed:", e)


def _push_event(conflict):
    conflict_id = (
        str(int(conflict.train_a)) + "_" +
        str(int(conflict.train_b)) + "_" +
        str(int(conflict.cell[0])) + "_" +
        str(int(conflict.cell[1]))
    )
    payload = {
        "use_case":    "Railway",
        "title":       "Conflict detected on network",
        "description": (
            "Conflict between Train " + str(int(conflict.train_a)) +
            " and Train " + str(int(conflict.train_b)) +
            " at cell " + str([int(x) for x in conflict.cell])
        ),
        "criticality": "HIGH",
        "start_date":  datetime.now(timezone.utc).isoformat(),
        "data": {
            # Platform-compatible fields
            "event_type":  "INFRASTRUCTURE",
            "id_train":    "Train_" + str(int(conflict.train_a)),
            "agent_id":    str(int(conflict.train_a)),
            "delay":       0,
            # Flatland-specific fields
            "train_b":     "Train_" + str(int(conflict.train_b)),
            "cell":        [int(x) for x in conflict.cell],
            "conflict_id": conflict_id,
            "message":     (
                "Conflict between Train " +
                str(int(conflict.train_a)) + " and Train " +
                str(int(conflict.train_b))
            ),
        }
    }
    token = _get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        requests.post(EVENT_SERVICE_URL, json=payload, headers=headers, timeout=5)
    except Exception as e:
        print("[push_event] Failed:", e)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/state")
def get_state():
    global scenario_player
    if scenario_player is not None:
        env  = scenario_player.env
        step = scenario_player.step
    else:
        with state_lock:
            env  = sim["env"]
            step = sim["step"]
        if env is None:
            return jsonify({"error": "simulation not initialised"}), 503

    trains = []
    for i, agent in enumerate(env.agents):
        try:
            state_str = agent.state.name if hasattr(agent.state, "name") else str(int(agent.state))
        except Exception:
            state_str = "UNKNOWN"
        pos = [int(x) for x in agent.position] if agent.position is not None else None
        trains.append({
            "id":        i,
            "position":  pos,
            "direction": int(agent.direction) if agent.direction is not None else 0,
            "state":     state_str,
        })
    return jsonify({"step": step, "trains": trains})


@app.route("/control", methods=["POST"])
def control():
    data    = request.get_json(force=True)
    command = data.get("command")

    if command in ("start", "resume"):
        with state_lock:
            sim["running"] = True
        return jsonify({"status": "running"})
    elif command == "pause":
        with state_lock:
            sim["running"] = False
        return jsonify({"status": "paused"})
    elif command == "reset":
        with state_lock:
            sim["running"] = False
        _init_simulation()
        return jsonify({"status": "reset"})
    elif command == "speed":
        value = float(data.get("value", 1.0))
        with state_lock:
            sim["speed"] = max(0.1, value)
        # Also update scenario player speed if active
        if scenario_player is not None:
            with scenario_player.lock:
                scenario_player.speed = max(0.1, value)
        return jsonify({"status": "ok", "speed": sim["speed"]})

    return jsonify({"error": "unknown command"}), 400


@app.route("/conflicts")
def get_conflicts():
    # ── Presentation mode: always return the static demo event ────────────
    # The real conflict detection still runs in the background (see
    # _check_for_conflict) and will override this if a real conflict is
    # detected. For the demo, comment out the two lines below to re-enable
    # real conflict detection.
    return jsonify({
        "conflict": PRESENTATION_EVENT,
        "options":  PRESENTATION_OPTIONS,
    })

    # ── Real conflict detection (kept for future use) ─────────────────────
    with state_lock:
        conflict = sim["active_conflict"]
        options  = sim["options"]

    if conflict is None:
        return jsonify({"conflict": None, "options": []})

    options_data = []
    for i, opt in enumerate(options):
        options_data.append({
            "index":           i,
            "train_to_delay":  int(opt.train_to_delay),
            "resolution_type": str(opt.resolution_type.value),
            "delay_added":     int(opt.delay_added),
            "description": (
                "Delay Train " + str(int(opt.train_to_delay)) +
                " by " + str(int(opt.delay_added)) + " steps" +
                " (" + str(opt.resolution_type.value) + ")"
            ),
        })

    return jsonify({
        "conflict": {
            "train_a":  int(conflict.train_a),
            "train_b":  int(conflict.train_b),
            "cell":     [int(x) for x in conflict.cell],
            "timestep": int(conflict.timestep),
        },
        "options": options_data,
    })


@app.route("/resolve", methods=["POST"])
def apply_resolution():
    data         = request.get_json(force=True)
    option_index = int(data.get("option_index", 0))

    with state_lock:
        conflict = sim["active_conflict"]
        options  = sim["options"]
        manager  = sim["manager"]

    if conflict is None:
        return jsonify({"error": "no active conflict"}), 400
    if option_index < 0 or option_index >= len(options):
        return jsonify({"error": "invalid option index"}), 400

    chosen = options[option_index]
    try:
        manager.apply_resolution_option(chosen)
        with state_lock:
            sim["dispatcher"].timetable = manager.timetable
            sim["dispatcher"]._init_routes(preserve_active=True)
            sim["active_conflict"]  = None
            sim["options"]          = []
            sim["conflict_pushed"]  = False
        return jsonify({"status": "applied", "option_index": option_index})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/render")
def render_map():
    global scenario_player

    # Use scenario player env if active, otherwise main sim
    if scenario_player is not None:
        env      = scenario_player.env
        renderer = None  # create fresh renderer for scenario env
    else:
        with state_lock:
            env      = sim["env"]
            renderer = sim["renderer"]
        if env is None or renderer is None:
            return jsonify({"error": "simulation not initialised"}), 503

    try:
        if renderer is None:
            # Use scenario player's cached renderer
            renderer = scenario_player.renderer

        image = renderer.render_env(
            show=False,
            show_observations=False,
            show_inactive_agents=True,
            show_rowcols=False,
            return_image=True,
        )
        if image is None:
            return jsonify({"error": "render returned None"}), 500

        pil_image = Image.fromarray(image.astype("uint8"))

        # Draw train IDs and event markers on the image
        from PIL import ImageDraw
        draw   = ImageDraw.Draw(pil_image)
        img_w, img_h = pil_image.size
        grid_h, grid_w = env.rail.grid.shape
        cell_w = img_w / grid_w
        cell_h = img_h / grid_h

        # Get affected trains (those with active event holds)
        affected = set()
        if scenario_player is not None:
            affected = scenario_player.get_affected_trains()

        for agent in env.agents:
            if agent.position is not None:
                row, col = agent.position
                x = int(col * cell_w)
                y = int(row * cell_h)
                # Red rectangle for affected trains
                if "Train_" + str(agent.handle) in affected:
                    pad = 4
                    draw.rectangle(
                        [x - pad, y - pad, x + int(cell_w) + pad, y + int(cell_h) + pad],
                        outline=(255, 0, 0), width=3
                    )
                # Train ID label
                # Yellow rectangle for user-selected train (CoLearning mode)
                if selected_train and selected_train == "Train_" + str(agent.handle):
                    pad2 = 6
                    draw.rectangle(
                        [x - pad2, y - pad2, x + int(cell_w) + pad2, y + int(cell_h) + pad2],
                        outline=(255, 200, 0), width=3
                    )
                label_color = (255, 80, 80) if "Train_" + str(agent.handle) in affected else (255, 255, 0)
                draw.text((x + 2, y + 2), "T" + str(agent.handle), fill=label_color)

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _push_presentation_event():
    """Push the static demo event card to event-service at startup."""
    import time
    time.sleep(5)  # Wait for services to be ready
    payload = {
        "use_case":    "Railway",
        "title":       "Heavy snowfall on route City_1 to City_0",
        "description": "Severe weather conditions affecting train services on this corridor.",
        "criticality": "HIGH",
        "start_date":  datetime.now(timezone.utc).isoformat(),
        "data": {
            "event_type":  "INFRASTRUCTURE",
            "id_train":    "Train_0",
            "agent_id":    "0",
            "delay":       0,
            "train_b":     "Train_1",
            "cell":        [15, 12],
            "conflict_id": "demo_event_1",
            "message":     "Heavy snowfall on route City_1 to City_0",
        }
    }
    token = _get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        response = requests.post(EVENT_SERVICE_URL, json=payload, headers=headers, timeout=5)
        print("[startup] Presentation event pushed, status:", response.status_code)
        if response.status_code not in (200, 201):
            print("[startup] Response:", response.text)
    except Exception as e:
        print("[startup] Failed to push presentation event:", e)


@app.route("/recommendations", methods=["GET", "POST"])
def get_recommendations():
    """
    External agent API endpoint called by recommendation-service.
    Returns resolution options in InteractiveAI's expected format.
    Called when operator clicks "Get recommendation" on an event card.
    """
    return jsonify([
        {
            "title":       "Reroute Train 0 via City_2",
            "description": "Reroute Train 0 via City_2 to avoid the affected corridor. Estimated additional delay: 8 minutes.",
            "use_case":    "Railway",
            "agent_type":  "AI",
            "actions":     [{"option_index": 0}],
            "kpis": {
                "delay":              "8 min",
                "nb_impacted_trains": "1",
                "best":               "True",
            }
        },
        {
            "title":       "Reroute Train 1 via City_0 bypass",
            "description": "Reroute Train 1 via the City_0 bypass line. Estimated additional delay: 6 minutes.",
            "use_case":    "Railway",
            "agent_type":  "AI",
            "actions":     [{"option_index": 1}],
            "kpis": {
                "delay":              "6 min",
                "nb_impacted_trains": "1",
                "best":               "False",
            }
        },
        {
            "title":       "Hold Train 0 at City_1 station",
            "description": "Hold Train 0 at City_1 station until track is cleared. Estimated wait: 12 minutes.",
            "use_case":    "Railway",
            "agent_type":  "AI",
            "actions":     [{"option_index": 2}],
            "kpis": {
                "delay":              "12 min",
                "nb_impacted_trains": "1",
                "best":               "False",
            }
        },
    ])



@app.route("/scenario/select", methods=["POST"])
def select_scenario():
    """Store selected scenario for map preview — called when user picks from dropdown."""
    global preview_scenario_id
    data = request.get_json(silent=True) or {}
    preview_scenario_id = data.get("scenario_id", "")
    return jsonify({"status": "ok", "scenario_id": preview_scenario_id})


@app.route("/transitions")
def get_transitions():
    """Rail grid transition table for ZWL frontend."""
    import json as _json
    # Use scenario env when active (may have different grid size)
    if scenario_player is not None:
        grid = scenario_player.env.rail.grid.tolist()
        return jsonify(grid)
    # Use preview scenario map when one is selected but no session running
    if preview_scenario_id:
        sc = ALL_SCENARIOS.get(preview_scenario_id)
        if sc:
            map_path = sc.get("map", "")
            if map_path.endswith(".json"):
                try:
                    with open(map_path, "r", encoding="utf-8") as f:
                        raw = _json.load(f)
                    return jsonify(raw["grid"])
                except Exception:
                    pass
    # Fall back to free-run simulation grid
    with state_lock:
        env = sim["env"]
        if env is None:
            return jsonify({"error": "simulation not initialised"}), 503
        grid = env.rail.grid.tolist()
    return jsonify(grid)


def _extract_target(agent):
    """Extract (row, col) target regardless of Flatland version."""
    for attr in ("target", "targets"):
        t = getattr(agent, attr, None)
        if t is None:
            continue
        # Simple (row, col) tuple/list
        if isinstance(t, (list, tuple)) and len(t) == 2 and isinstance(t[0], int):
            return [int(t[0]), int(t[1])]
        # Set of ((row,col), direction) — Flatland 4.x pkl format
        if isinstance(t, (set, frozenset)):
            for item in t:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pos = item[0]
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        return [int(pos[0]), int(pos[1])]
    return None


def _compute_marey_mapping(map_path, start_rc, end_rc):
    """BFS through grid from start to end, returns {r,c: distance} mapping."""
    import json as _json
    from collections import deque
    try:
        with open(map_path, "r") as f:
            raw = _json.load(f)
        grid = raw["grid"]
    except Exception:
        return {}
    rows, cols = len(grid), len(grid[0])
    dist = {start_rc: 0}
    queue = deque([start_rc])
    directions = [(-1,0),(0,1),(1,0),(0,-1)]
    while queue:
        r, c = queue.popleft()
        for dr, dc in directions:
            nr, nc = r+dr, c+dc
            if 0 <= nr < rows and 0 <= nc < cols                and grid[nr][nc] != 0                and (nr, nc) not in dist:
                dist[(nr, nc)] = dist[(r,c)] + 1
                queue.append((nr, nc))
    return {f"{r},{c}": d for (r,c), d in dist.items()}


@app.route("/mapping")
def get_mapping():
    """Return linearized position mapping for Marey diagram."""
    sc = None
    if scenario_player is not None:
        sc = scenario_player.scenario
    elif preview_scenario_id:
        sc = ALL_SCENARIOS.get(preview_scenario_id)
    if sc is None:
        return jsonify({})
    link = sc.get("marey_link")
    if not link:
        return jsonify({})
    map_path = sc.get("map", "")
    if not map_path.endswith(".json"):
        return jsonify({})
    start = tuple(link["start"])
    end   = tuple(link["end"])
    mapping = _compute_marey_mapping(map_path, start, end)
    return jsonify(mapping)


@app.route("/stations")
def get_stations():
    """Return station positions for the current or preview scenario map."""
    # Determine which scenario to use
    sc = None
    if scenario_player is not None:
        sc = scenario_player.scenario
    elif preview_scenario_id:
        sc = ALL_SCENARIOS.get(preview_scenario_id)

    if sc is None:
        return jsonify([])

    stations = []
    map_path = sc.get("map", "")
    if map_path.endswith(".json"):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for s in raw.get("stations", []):
                stations.append({
                    "id":   s["id"],
                    "r":    s["r"],
                    "c":    s["c"],
                    "name": f"Station {s['id']}",
                })
        except Exception:
            pass

    # Agent start positions as station markers
    for i, adef in enumerate(sc.get("agent_defs", [])):
        r, c = adef["start"]
        stations.append({
            "id":   f"start_{i}",
            "r":    r,
            "c":    c,
            "name": adef.get("name", f"Train_{i}"),
            "type": "start",
        })
    return jsonify(stations)


@app.route("/agents")
def get_agents():
    """Current agent states for ZWL frontend."""
    active_env = scenario_player.env if scenario_player is not None else None
    if active_env is None:
        with state_lock:
            active_env = sim["env"]
    if active_env is None:
        return jsonify({"error": "simulation not initialised"}), 503

    # Build train name map from scenario agent_defs
    train_names = {}
    if scenario_player is not None:
        for i, adef in enumerate(scenario_player.scenario.get("agent_defs", [])):
            train_names[i] = adef.get("name", f"Train_{i}")

    agents = []
    for agent in active_env.agents:
        agents.append({
            "position":    [int(c) for c in agent.position] if agent.position is not None else None,
            "direction":   int(agent.direction) if agent.direction is not None else 0,
            "moving":      bool(agent.moving) if hasattr(agent, "moving") else False,
            "target":      _extract_target(agent),
            "malfunction": 0,
            "name":        train_names.get(agent.handle, f"Train_{agent.handle}"),
        })
    return jsonify(agents)


@app.route("/history")
def get_history():
    """Full simulation history for ZWL Marey diagram."""
    global scenario_player
    if scenario_player is not None:
        return jsonify(scenario_player.get_history_steps())
    with state_lock:
        history = list(sim["history"])
    return jsonify(history)


@app.route("/plans")
def get_plans():
    """Plans endpoint — returns current history as single plan."""
    with state_lock:
        history = list(sim["history"])
    return jsonify([history])


def _push_resolved_event_card(scenario: dict):
    """Push an ND (resolved) notification after a decision is applied."""
    import time as _time
    start_ms = int(_time.time() * 1000)
    payload = {
        "publisher":        "publisher_test",
        "processVersion":   "1",
        "process":          "cabProcess",
        "processInstanceId": "scenario_resolved_" + scenario.get("id", "unknown"),
        "state":            "messageState",
        "groupRecipients":  ["Dispatcher", "Planner", "ReadOnly"],
        "entityRecipients": ["Railway"],
        "severity":         "INFORMATIONAL",
        "startDate":        start_ms,
        "summary": {
            "key":        "cabProcess.summary",
            "parameters": {"summary": "Störung behoben — Lösung angewendet."},
        },
        "title": {
            "key":        "cabProcess.title",
            "parameters": {"title": "Gelöst: " + scenario.get("name", "Ereignis")},
        },
        "data": {
            "metadata":    {"event_type": "INFRASTRUCTURE", "id_train": "Train_3"},
            "criticality": "ND",
        }
    }
    try:
        r = requests.post("http://localhost:2102/cards", json=payload, timeout=5)
        print(f"[scenario] Resolved card pushed → {r.status_code}")
        pid = payload.get("processInstanceId", "")
        if pid and pid not in pushed_process_instance_ids:
            pushed_process_instance_ids.append(pid)
    except Exception as e:
        print(f"[scenario] Failed to push resolved card: {e}")


def _delete_all_pushed_cards():
    """Clear all pushed notification cards. Fail-safe — never crashes session_start."""
    global pushed_card_ids, pushed_process_instance_ids
    try:
        ts_ms = int(__import__("time").time() * 1000)
        # Only send ND for cards actually pushed this session — avoids 404s on first run
        all_pids = set(pid for pid in pushed_process_instance_ids if pid)
        for pid in all_pids:
            payload = {
                "publisher": "publisher_test", "processVersion": "1",
                "process": "cabProcess", "processInstanceId": pid,
                "state": "messageState",
                "groupRecipients": ["Dispatcher", "Planner", "ReadOnly"],
                "entityRecipients": ["Railway"], "severity": "INFORMATIONAL",
                "startDate": ts_ms - 10000, "endDate": ts_ms - 1,
                "expirationDate": ts_ms - 1,
                "summary": {"key": "cabProcess.summary", "parameters": {"summary": "Gelöscht"}},
                "title":   {"key": "cabProcess.title",   "parameters": {"title":   "Gelöscht"}},
                "data":    {"criticality": "ND"},
            }
            try:
                requests.post("http://localhost:2102/cards", json=payload, timeout=2)
            except Exception:
                pass
        pushed_card_ids = []
        pushed_process_instance_ids = []
    except Exception as e:
        print(f"[notify] _delete_all_pushed_cards failed (non-fatal): {e}")
        pushed_card_ids = []
        pushed_process_instance_ids = []

def _push_scenario_event_card(event: dict):
    """
    Push a scenario event card directly to cards-publication (port 2102).
    This bypasses auth — same approach as sendCard.sh which works reliably.
    Skip if event has push_card=False.
    """
    if not event.get("push_card", True):
        return  # event suppresses card notification
    import time as _time
    start_date_ms = int(_time.time() * 1000)
    payload = {
        "publisher":        "publisher_test",
        "processVersion":   "1",
        "process":          "cabProcess",
        "processInstanceId": "scenario_event_" + str(event.get("timestep", 0)),
        "state":            "messageState",
        "groupRecipients":  ["Dispatcher", "Planner", "ReadOnly"],
        "entityRecipients": ["Railway"],
        "severity":         "ALARM",
        "startDate":        start_date_ms,
        "summary": {
            "key":        "cabProcess.summary",
            "parameters": {"summary": event.get("card_description", "")},
        },
        "title": {
            "key":        "cabProcess.title",
            "parameters": {"title": event.get("card_title", "Event on network")},
        },
        "data": {
            "metadata":    {
                "event_type": "INFRASTRUCTURE",
                "id_train":   event.get("train", "Train_0"),
                "conflict_id": "scenario_event_" + str(event.get("timestep", 0)),
            },
            "criticality": "HIGH",
        }
    }
    try:
        r = requests.post("http://localhost:2102/cards", json=payload, timeout=5)
        print("[scenario] Event card pushed:", event.get("card_title"), "→", r.status_code)
        # Track processInstanceId for clearing via ND on next session start
        pid = payload.get("processInstanceId", "")
        if pid and pid not in pushed_process_instance_ids:
            pushed_process_instance_ids.append(pid)
    except Exception as e:
        print("[scenario] Failed to push event card:", e)


# ── Scenario / Session endpoints ───────────────────────────────────────────────

@app.route("/session/start", methods=["POST"])
def session_start():
    """
    Start a new session. Returns session_id and first scenario info.
    POST body: {} (optional: {"scenario_ids": ["test", ...]})
    """
    global scenario_player
    data         = request.get_json(force=True) or {}
    scenario_ids = data.get("scenario_ids", list(ALL_SCENARIOS.keys()))

    global session_mode
    session_mode = data.get("mode", "recommendation")
    acronym      = data.get("acronym", "")
    session_id   = SessionManager.create_session(scenario_ids, acronym=acronym, mode=session_mode)
    scenario_id  = SessionManager.current_scenario_id(session_id)
    scenario     = ALL_SCENARIOS.get(scenario_id)

    if scenario is None:
        return jsonify({"error": "No scenarios available"}), 400

    # Clean up old scenario cards from MongoDB so they don't replay on login
    try:
        old_ids = ["cabProcess.scenario_event_0", "cabProcess.scenario_event_1",
                   "cabProcess.scenario_event_15", "cabProcess.scenario_event_30"]
        for cid in old_ids:
            requests.delete(f"http://localhost:2102/cards/{cid}", timeout=2)
    except Exception:
        pass  # cleanup is best-effort

    # Event callback — pushes scenario events as notification cards
    def push_scenario_event(event: dict):
        threading.Thread(
            target=_push_scenario_event_card,
            args=(event,),
            daemon=True
        ).start()

    # Start scenario player
    # Clear previous scenario notifications
    threading.Thread(target=_delete_all_pushed_cards, daemon=True).start()

    scenario_player = ScenarioPlayer(scenario, on_event=push_scenario_event)
    scenario_player.start()

    return jsonify({
        "session_id":    session_id,
        "scenario_id":   scenario_id,
        "scenario_name": scenario["name"],
        "total_scenarios": len(scenario_ids),
        "current_index": 1,
    })


@app.route("/session/status")
def session_status():
    """Current scenario player status — polled by frontend."""
    global scenario_player, session_mode
    if scenario_player is None:
        return jsonify({"state": "idle", "mode": session_mode})
    status = scenario_player.get_status()
    status["mode"] = session_mode
    # Add active session_id so frontend can use it for decisions
    for sid, sess in _sessions.items():
        status["session_id"] = sid
        break
    # Add conflict trains for CoLearning mode
    if session_mode == "colearning" and status.get("active_decision"):
        # Read outcomes directly from scenario definition (not from status options which strip outcomes)
        scenario_dps = scenario_player.scenario.get("decision_points", [])
        dp_index = scenario_player.decision_index - 1
        dp = scenario_dps[dp_index] if dp_index < len(scenario_dps) else {}

        # Use scenario-level colearning_config override if defined
        cl_config = scenario_player.scenario.get("colearning_config")
        if cl_config:
            trains = set(cl_config.get("trains", []))
            train_actions = {t: list(cl_config.get("actions", ["warten"])) for t in trains}
        else:
            trains = set()
            train_actions = {}

        # Collect ALL trains mentioned anywhere in the options
        all_dp_trains: set = set()
        for opt in dp.get("options", []):
            outcome = opt.get("outcome", {})
            if outcome.get("hold_train"):
                all_dp_trains.add(outcome["hold_train"])
            all_dp_trains.update(outcome.get("hold_trains", []))
            all_dp_trains.update(outcome.get("holds", {}).keys())
            all_dp_trains.update(outcome.get("scripted_actions", {}).keys())

        if not cl_config:
            # Pass 1: collect all "warten" trains
            for opt in dp.get("options", []):
                outcome = opt.get("outcome", {})
                ht  = outcome.get("hold_train")
                hts = list(outcome.get("hold_trains", [])) + list(outcome.get("holds", {}).keys())
                if ht:
                    trains.add(ht)
                    train_actions.setdefault(ht, [])
                    if "warten" not in train_actions[ht]:
                        train_actions[ht].append("warten")
                for t in hts:
                    trains.add(t)
                    train_actions.setdefault(t, [])
                    if "warten" not in train_actions[t]:
                        train_actions[t].append("warten")
            # Pass 2: add "umleiten" only for trains not already covered by warten
            for opt in dp.get("options", []):
                outcome = opt.get("outcome", {})
                for t in outcome.get("scripted_actions", {}):
                    if t not in trains:
                        trains.add(t)
                        train_actions.setdefault(t, [])
                        if "umleiten" not in train_actions[t]:
                            train_actions[t].append("umleiten")
            # Pass 3: add "vorfahrt" to trains that appear as priority in any option
            for opt in dp.get("options", []):
                outcome = opt.get("outcome", {})
                held = set(outcome.get("hold_trains", []))
                held |= set(outcome.get("holds", {}).keys())
                if outcome.get("hold_train"):
                    held.add(outcome["hold_train"])
                if held:
                    for t in all_dp_trains:
                        if t not in held:
                            trains.add(t)
                            train_actions.setdefault(t, [])
                            if "vorfahrt" not in train_actions[t]:
                                train_actions[t].append("vorfahrt")
        status["conflict_trains"] = sorted(trains)
        status["train_actions"]   = train_actions

        # Build kpis_by_train: for each selectable train → its matched option's KPIs
        kpis_by_train = {}
        for opt in dp.get("options", []):
            outcome = opt.get("outcome", {})
            kpis    = opt.get("kpis", {})
            held = set(outcome.get("hold_trains", []))
            held |= set(outcome.get("holds", {}).keys())
            if outcome.get("hold_train"):
                held.add(outcome["hold_train"])
            for t in trains:
                if t not in held:
                    # This train gets priority in this option
                    kpis_by_train[t] = kpis
        status["kpis_by_train"] = kpis_by_train
    # Include currently selected train for ZWL map highlight
    status["selected_train"] = selected_train
    # Human-readable train names from scenario agent_defs
    train_names = {}
    for i, adef in enumerate(scenario_player.scenario.get("agent_defs", [])):
        train_names[f"Train_{i}"] = adef.get("name", f"Train_{i}")
    status["train_names"] = train_names
    return jsonify(status)


@app.route("/session/decision", methods=["POST"])
def session_decision():
    """
    Apply a decision at the current decision point.
    Body: {
        "session_id": "...",
        "option_index": 0
    }
    """
    global scenario_player
    data         = request.get_json(force=True)
    session_id   = data.get("session_id", "")
    option_index = int(data.get("option_index", 0))

    print(f"[decision] Received decision: option_index={option_index}, session_id={session_id!r}")

    if scenario_player is None:
        print("[decision] ERROR: No active scenario player")
        return jsonify({"error": "No active scenario"}), 400

    status = scenario_player.get_status()
    print(f"[decision] Current state: {status['state']}, step: {status['step']}")

    if status["state"] != ScenarioState.PAUSED:
        print(f"[decision] ERROR: Not paused — state is {status['state']}")
        return jsonify({"error": "Not at a decision point"}), 400

    decision = status["active_decision"]
    if decision is None or option_index >= len(decision["options"]):
        return jsonify({"error": "Invalid option index"}), 400

    option_label = decision["options"][option_index]["label"]
    kpis         = decision["options"][option_index]["kpis"]

    # Get scenario_id from the player directly (session_id may be empty if started from Timeline)
    scenario_id = scenario_player.scenario.get("id", "unknown")
    decision_index = scenario_player.decision_index - 1

    SessionManager.log_decision(
        session_id or "anonymous", scenario_id, decision_index, option_index, option_label
    )

    # Apply decision and resume
    success = scenario_player.apply_decision(option_index)
    print(f"[decision] apply_decision returned: {success}, new state: {scenario_player.state}")

    # Store for experiment log
    global last_decision
    last_decision = {
        "type":         "recommendation",
        "option_index": option_index,
        "option_label": option_label,
        "kpis":         kpis,
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }

    # Push ND (resolved) notification to InteractiveAI
    threading.Thread(
        target=_push_resolved_event_card,
        args=(scenario_player.scenario,),
        daemon=True
    ).start()

    return jsonify({
        "status":       "applied",
        "option_index": option_index,
        "option_label": option_label,
        "kpis":         kpis,
    })


@app.route("/session/next", methods=["POST"])
def session_next():
    """
    Advance to the next scenario after current one completes.
    Body: {"session_id": "..."}
    """
    global scenario_player
    data       = request.get_json(force=True)
    session_id = data.get("session_id", "")

    has_next = SessionManager.advance_scenario(session_id)

    if not has_next:
        scenario_player = None
        decisions = SessionManager.get_decisions(session_id)
        return jsonify({
            "status":    "session_complete",
            "decisions": decisions,
        })

    scenario_id = SessionManager.current_scenario_id(session_id)
    scenario    = ALL_SCENARIOS.get(scenario_id)

    if scenario is None:
        return jsonify({"error": "Scenario not found"}), 400

    def push_scenario_event_next(event: dict):
        threading.Thread(
            target=_push_scenario_event_card,
            args=(event,),
            daemon=True
        ).start()

    scenario_player = ScenarioPlayer(scenario, on_event=push_scenario_event_next)
    scenario_player.start()

    return jsonify({
        "status":        "next_scenario",
        "scenario_id":   scenario_id,
        "scenario_name": scenario["name"],
    })


@app.route("/session/selected_train", methods=["POST"])
def set_selected_train():
    """Store which train the user has selected in CoLearning mode (for map highlight)."""
    global selected_train
    data = request.get_json(force=True)
    selected_train = data.get("train", "")
    return jsonify({"status": "ok", "selected_train": selected_train})


@app.route("/experiment/log", methods=["POST"])
def experiment_log():
    """
    Save a complete experiment run as a human-readable JSON file.
    Called by the test module after scenario + reflection are complete.
    Body: { participant_id, mode, scenario_id, decision, reflection_answers }
    """
    global last_decision, session_mode, scenario_player
    data = request.get_json(force=True)

    scenario_id   = data.get("scenario_id", "")
    scenario_name = data.get("scenario_name", "")
    if scenario_player is not None:
        scenario_id   = scenario_player.scenario.get("id", scenario_id)
        scenario_name = scenario_player.scenario.get("name", scenario_name)

    log = {
        "experiment_id":  f"exp_{data.get('participant_id','?')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "participant_id": data.get("participant_id", ""),
        "type":           "test_run",
        "started_at":     data.get("started_at", datetime.now(timezone.utc).isoformat()),
        "completed_at":   datetime.now(timezone.utc).isoformat(),
        "szenario": {
            "id":   scenario_id,
            "name": scenario_name,
            "modus": session_mode,
        },
        "entscheidung": last_decision or data.get("decision", {}),
        "reflexion": data.get("reflection_answers", []),
    }

    filename = save_experiment_log(log)
    return jsonify({"status": "gespeichert", "datei": filename, "log": log})


@app.route("/experiment/logs")
def list_experiment_logs():
    """List all saved experiment log files."""
    files = list_logs()
    return jsonify({"count": len(files), "files": files})


@app.route("/experiment/logs/<filename>")
def get_experiment_log(filename: str):
    """Return content of a specific experiment log file."""
    import os
    log_path = os.path.join("experiment_logs", filename)
    if not os.path.exists(log_path):
        return jsonify({"error": "Datei nicht gefunden"}), 404
    data = read_log(filename)
    return jsonify(data)


@app.route("/reflection", methods=["POST"])
def save_reflection():
    """
    Save reflection module answers.
    Body: { "session_id": "...", "acronym": "...", "answers": [{question_index, question_text, answer}] }
    """
    data       = request.get_json(force=True)
    session_id = data.get("session_id", "")
    acronym    = data.get("acronym", "")
    answers    = data.get("answers", [])
    SessionManager.log_reflection(session_id, acronym, answers)
    print(f"[reflection] Logged {len(answers)} answers for {acronym or 'anonymous'}")
    return jsonify({"status": "saved", "count": len(answers)})


@app.route("/reflection/<session_id>")
def get_reflection(session_id: str):
    """Return reflection answers for a session."""
    return jsonify(SessionManager.get_reflections(session_id))


@app.route("/session/colearning_action", methods=["POST"])
def colearning_action():
    """
    Apply a user-defined CoLearning action.
    Body: { "session_id": "...", "train": "Train_0", "action": "warten" | "umleiten" }
    Matches the user's choice to the closest predefined option in the scenario.
    """
    global scenario_player, session_mode
    data       = request.get_json(force=True)
    session_id = data.get("session_id", "")
    train_id   = data.get("train", "")     # e.g. "Train_0"
    action     = data.get("action", "")    # "warten" or "umleiten"

    if scenario_player is None:
        return jsonify({"error": "Kein aktives Szenario"}), 400

    status = scenario_player.get_status()
    if status["state"] != ScenarioState.PAUSED:
        return jsonify({"error": "Kein Entscheidungspunkt aktiv"}), 400

    # Get decision point directly from scenario definition (outcomes not in status)
    scenario_dps = scenario_player.scenario.get("decision_points", [])
    dp_index = scenario_player.decision_index - 1
    if dp_index < 0 or dp_index >= len(scenario_dps):
        return jsonify({"feasible": False, "message": "Kein aktiver Entscheidungspunkt."}), 200

    dp = scenario_dps[dp_index]

    # Block actions marked as invalid in colearning_config
    cl_cfg = scenario_player.scenario.get("colearning_config", {})
    if action in cl_cfg.get("invalid_actions", []):
        return jsonify({
            "feasible": False,
            "message":  "Diese Aktion ist für dieses Szenario nicht möglich.",
        }), 200

    matching_index  = None
    matching_option = None

    for i, opt in enumerate(dp.get("options", [])):
        outcome = opt.get("outcome", {})
        if action == "warten" and outcome.get("hold_train") == train_id:
            matching_index  = i
            matching_option = opt
            break
        elif action == "warten" and train_id in outcome.get("hold_trains", []):
            matching_index  = i
            matching_option = opt
            break
        elif action == "vorfahrt" and train_id not in outcome.get("hold_trains", [])                 and train_id not in outcome.get("holds", {})                 and train_id != outcome.get("hold_train"):
            matching_index  = i
            matching_option = opt
            break
        elif action == "umleiten" and "scripted_actions" in outcome and train_id in outcome["scripted_actions"]:
            matching_index  = i
            matching_option = opt
            break

    if matching_option is None:
        return jsonify({
            "feasible": False,
            "message": f"Keine Lösung für '{action}' mit {train_id} verfügbar."
        }), 200

    # Log and apply
    scenario_id    = scenario_player.scenario.get("id", "unknown")
    decision_index = scenario_player.decision_index - 1
    SessionManager.log_decision(
        session_id or "anonymous",
        scenario_id,
        decision_index,
        matching_index,
        f"[Ko-Lernen] {action}: {train_id}"
    )
    scenario_player.apply_decision(matching_index)

    # Store for experiment log
    global last_decision
    last_decision = {
        "type":         "colearning",
        "train":        train_id,
        "action":       action,
        "option_index": matching_index,
        "option_label": matching_option["label"],
        "kpis":         matching_option["kpis"],
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }

    # Push ND (resolved) notification
    threading.Thread(
        target=_push_resolved_event_card,
        args=(scenario_player.scenario,),
        daemon=True
    ).start()

    return jsonify({
        "feasible":     True,
        "applied":      True,
        "option_index": matching_index,
        "option_label": matching_option["label"],
        "kpis":         matching_option["kpis"],
    })


@app.route("/session/decisions")
def session_decisions():
    """Return all logged decisions for a session (for end screen)."""
    session_id = request.args.get("session_id", "")
    decisions  = SessionManager.get_decisions(session_id)
    return jsonify(decisions)


@app.route("/session/stop", methods=["POST"])
def session_stop():
    """Stop the active scenario player and return to free-run mode."""
    global scenario_player
    _delete_all_pushed_cards()
    if scenario_player is not None:
        scenario_player.running = False
        scenario_player = None
    return jsonify({"status": "stopped"})


@app.route("/session/render")
def session_render():
    """
    Render the current scenario frame as PNG.
    Falls back to main sim render if no scenario active.
    """
    global scenario_player
    if scenario_player is None:
        return render_map()  # use existing render endpoint

    try:
        from flatland.utils.rendertools import RenderTool
        from PIL import Image
        renderer = RenderTool(
            scenario_player.env, gl="PILSVG",
            screen_width=600, screen_height=600
        )
        image = renderer.render_env(
            show=False,
            show_observations=False,
            show_inactive_agents=True,
            show_rowcols=False,
            return_image=True,
        )
        if image is None:
            return jsonify({"error": "render failed"}), 500

        pil_image = Image.fromarray(image.astype("uint8"))

        # Draw train IDs
        from PIL import ImageDraw
        draw   = ImageDraw.Draw(pil_image)
        img_w, img_h = pil_image.size
        grid_h, grid_w = scenario_player.env.rail.grid.shape
        for agent in scenario_player.env.agents:
            if agent.position is not None:
                row, col = agent.position
                x = int(col * img_w / grid_w)
                y = int(row * img_h / grid_h)
                draw.text((x + 2, y + 2), "T" + str(agent.handle), fill=(255, 255, 0))

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/session/history")
def session_history():
    """History of agent positions for ZWL diagram during scenario."""
    global scenario_player
    if scenario_player is None:
        return get_history()  # fall back to main sim history
    # Collect history from scenario player's env steps
    with sim["env"] and True:
        pass
    return jsonify([])  # ZWL will use main /history for now


@app.route("/scenarios")
def list_scenarios():
    """List all available scenarios."""
    return jsonify([
        {"id": sid, "name": s["name"]}
        for sid, s in ALL_SCENARIOS.items()
    ])

if __name__ == "__main__":
    _init_simulation()
    threading.Thread(target=_sim_loop,                daemon=True).start()
    threading.Thread(target=_snapshot_loop,           daemon=True).start()
    # _push_presentation_event disabled — scenario events replace this
    # threading.Thread(target=_push_presentation_event, daemon=True).start()
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
