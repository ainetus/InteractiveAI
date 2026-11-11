"""
The Railway simulator's HTTP app (Flask, as PowerGrid's simulator), reached by the browser only
through the frontend nginx's /railway-simu/ (the dev gateway on the dev stack). Not a status
source: everything the page shows comes from the contexts and the cards (D5, D11).

    GET  /health
    GET  /api/v1/scenarios           id, name and introduction of every scenario (static, Q26 a)
    POST /api/v1/session             start: {"session_id", "kind": "experiment"} or
                                     {"session_id", "kind": "single", "scenario_id", "mode"}
                                     201 with the session; 409 if this session_id is running
    POST /api/v1/session/next        start run 1, or the next run after a complete one
    POST /api/v1/session/stop        "✕ Beenden": end the session
    POST /api/v1/recommendations     the applied choice: actions[0] of the recommendation
                                     ({"scenario_id", "decision_index", "option_index"[, "train",
                                     "action"]}) and the card's "event_id"; 409 when it is not the
                                     open decision (§4.2.5)

Settings (environment): RAILWAY_STEPS_PER_SECOND (default 1), RAILWAY_SIMU_HOST (default
0.0.0.0), RAILWAY_SIMU_PORT (default 5124), and the Publisher's (integration/publisher.py).
Run: python app.py
"""

import logging
import os

from flask import Flask, jsonify, request

from experiment_scenarios import ALL_SCENARIOS
from integration.loop import Conflict, SessionRunner
from integration.publisher import Publisher
from integration.session import experiment_runs, single_run


def create_app(runner: SessionRunner = None) -> Flask:
    app = Flask(__name__)
    if runner is None:
        runner = SessionRunner(Publisher.from_env(),
                               steps_per_second=float(os.getenv("RAILWAY_STEPS_PER_SECOND", "1")))
    app.config["RUNNER"] = runner

    @app.errorhandler(Conflict)
    def conflict(error):
        return jsonify({"error": str(error)}), 409

    @app.errorhandler(ValueError)
    def bad_request(error):
        return jsonify({"error": str(error)}), 400

    def body() -> dict:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("a JSON object is expected")
        return data

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/v1/scenarios")
    def scenarios():
        return jsonify([{"id": sid, "name": sc["name"], "introduction": sc.get("introduction", "")}
                        for sid, sc in ALL_SCENARIOS.items()])

    @app.post("/api/v1/session")
    def start_session():
        data = body()
        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id is required")
        kind = data.get("kind", "experiment")
        if kind == "experiment":
            runs = experiment_runs(session_id, list(ALL_SCENARIOS))
        elif kind == "single":
            runs = single_run(data.get("scenario_id"), data.get("mode"))
        else:
            raise ValueError(f"unknown kind {kind!r}")
        return jsonify(runner.start_session(session_id, runs)), 201

    @app.post("/api/v1/session/next")
    def next_run():
        return jsonify(runner.next_run())

    @app.post("/api/v1/session/stop")
    def stop_session():
        return jsonify(runner.stop_session())

    @app.post("/api/v1/recommendations")
    def apply_recommendation():
        data = body()
        action = {k: v for k, v in data.items() if k != "event_id"}
        return jsonify({"applied": runner.apply(action, data.get("event_id"))})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    application = create_app()
    application.config["RUNNER"].start()
    application.run(host=os.getenv("RAILWAY_SIMU_HOST", "0.0.0.0"),
                    port=int(os.getenv("RAILWAY_SIMU_PORT", "5124")), threaded=True)
