"""Recommendation jobs: agents asked in the background, polled one by one."""

import threading
import time
from datetime import datetime, timedelta

import pytest
import requests
from api.models import RecommendationJobAgent, UseCaseModel, db
from api.utils import load_usecases_db

HEADERS = {"Authorization": "Bearer token"}
REQUEST = {"event": {"event_type": "KPI"}, "context": {"observation": {}}}


@pytest.fixture
def powergrid(app, client, monkeypatch):
    """The PowerGrid use case with a fast agent and a slow one, logged in."""
    monkeypatch.setenv("RL_AGENT_API_URL", "http://fast/api/v1/recommendation")
    monkeypatch.setenv("RL_AGENT_NAME", "Fast")
    monkeypatch.setenv("RL_AGENT_2_API_URL", "http://slow/api/v1/recommendation")
    monkeypatch.setenv("RL_AGENT_2_NAME", "Slow")
    monkeypatch.setattr(
        "cab_common_auth.decorators.keycloak.introspect",
        lambda token: {"active": True, "entitiesId": "PowerGrid", "groups": ""},
    )
    db.session.add(UseCaseModel(name="PowerGrid", manager_class="PowerGridManager"))
    db.session.commit()
    load_usecases_db(app.use_case_factory)
    return app


@pytest.fixture
def agents(monkeypatch):
    """Fake agents: "fast" answers at once, "slow" when released, "down" fails."""
    slow_release = threading.Event()
    calls = []

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    def post(url, json, **kwargs):
        calls.append((url, json))
        if url.startswith("http://slow"):
            slow_release.wait(5)
            return Response([{"title": "Slow reco", "actions": [{}]}])
        if url.startswith("http://down"):
            raise requests.exceptions.ConnectionError("refused")
        return Response([{"title": "Fast reco", "actions": [{}]}])

    monkeypatch.setattr("resources.PowerGrid.manager.requests.post", post)
    return slow_release, calls


def poll(client, job_id, until, timeout=5):
    deadline = time.monotonic() + timeout
    while True:
        response = client.get(f"/api/v1/recommendation/jobs/{job_id}", headers=HEADERS)
        assert response.status_code == 200
        if until(response.json) or time.monotonic() > deadline:
            return response.json
        time.sleep(0.02)


def test_job_shows_each_agent_as_it_answers(client, powergrid, agents):
    slow_release, calls = agents
    response = client.post("/api/v1/recommendation/jobs", headers=HEADERS, json=REQUEST)
    assert response.status_code == 202
    job = response.json
    assert job["status"] == "running"
    assert [a["id"] for a in job["agents"]] == ["agent1", "agent2"]

    # The fast agent's recommendations, while the slow one is still working
    job = poll(client, job["id"], lambda j: j["agents"][0]["status"] == "done")
    assert job["status"] == "running"
    assert job["agents"][1]["status"] == "pending"
    assert [r["title"] for r in job["recommendations"]] == ["Fast reco · Fast"]
    assert job["recommendations"][0]["agent_name"] == "Fast"

    slow_release.set()
    job = poll(client, job["id"], lambda j: j["status"] == "done")
    assert [a["status"] for a in job["agents"]] == ["done", "done"]
    assert [r["title"] for r in job["recommendations"]] == [
        "Fast reco · Fast",
        "Slow reco · Slow",
    ]
    # The agents get the request as before, without "agents"
    assert all(body == REQUEST for _, body in calls)


def test_job_asks_only_the_chosen_agents(client, powergrid, agents):
    _, calls = agents
    response = client.post(
        "/api/v1/recommendation/jobs",
        headers=HEADERS,
        json={**REQUEST, "agents": ["agent1"]},
    )
    job = poll(client, response.json["id"], lambda j: j["status"] == "done")
    assert [a["id"] for a in job["agents"]] == ["agent1"]
    assert [url for url, _ in calls] == ["http://fast/api/v1/recommendation"]


def test_agent_that_fails_is_reported(client, powergrid, agents, monkeypatch):
    monkeypatch.setenv("RL_AGENT_2_API_URL", "http://down/api/v1/recommendation")
    load_usecases_db(powergrid.use_case_factory)
    response = client.post("/api/v1/recommendation/jobs", headers=HEADERS, json=REQUEST)
    job = poll(client, response.json["id"], lambda j: j["status"] == "done")
    assert [a["status"] for a in job["agents"]] == ["done", "failed"]
    assert [r["title"] for r in job["recommendations"]] == ["Fast reco · Fast"]


def test_agent_past_its_deadline_is_reported_failed(client, powergrid, agents):
    # The slow agent never answers: as after a restart of the service
    response = client.post("/api/v1/recommendation/jobs", headers=HEADERS, json=REQUEST)
    job_id = response.json["id"]
    row = RecommendationJobAgent.query.filter_by(job_id=job_id, agent_id="agent2").one()
    row.deadline = datetime.utcnow() - timedelta(seconds=1)
    db.session.commit()

    job = poll(client, job_id, lambda j: j["status"] == "done")
    assert job["agents"][1]["status"] == "failed"


def test_unknown_job_is_not_found(client, powergrid):
    response = client.get("/api/v1/recommendation/jobs/nope", headers=HEADERS)
    assert response.status_code == 404


def test_synchronous_recommendation_is_unchanged(client, powergrid, agents, monkeypatch):
    monkeypatch.setenv("RL_AGENT_2_API_URL", "http://down/api/v1/recommendation")
    load_usecases_db(powergrid.use_case_factory)
    response = client.post("/api/v1/recommendation", headers=HEADERS, json=REQUEST)
    assert response.status_code == 200
    # The agent that fails gives no recommendation, as before
    assert [r["title"] for r in response.json] == ["Fast reco · Fast"]
