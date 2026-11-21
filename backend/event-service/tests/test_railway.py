"""Railway events: the fields of the scripted simulator (usecases_examples/Railway/) and today's
payloads are both accepted; unknown fields are still rejected."""

import pytest

from api.models import UseCaseModel, db
from api.utils import load_usecases_db

HEADERS = {"Authorization": "Bearer railway-test-token"}

TODAY_EVENT = {
    "use_case": "Railway",
    "criticality": "HIGH",
    "title": "Signalstörung",
    "description": "Seed event of the dev stack, in today's Railway schema.",
    "start_date": "2026-11-20T09:00:00+00:00",
    "data": {"event_type": "INFRASTRUCTURE", "id_train": "AB001", "agent_id": "0",
             "id_event": None, "delay": 15},
}

SIMULATOR_EVENT = {
    "use_case": "Railway",
    "criticality": "HIGH",
    "title": "Dispositionskonflikt — G 3 fährt langsam",
    "description": "G 3 fährt mit halber Geschwindigkeit und blockiert den Streckenabschnitt.",
    "start_date": "2026-11-20T09:00:16+00:00",
    "data": {
        "id_event": "4f1c_scenario3_16",
        "event_type": "INFRASTRUCTURE",
        "id_train": "Train_0",
        "agent_id": "0",
        "delay": 0,
        "scenario_id": "scenario3",
        "timestep": 16,
        "decision_index": 0,
        "session_id": "4f1c",
        "run_mode": "colearning",
    },
}


@pytest.fixture
def railway_auth_mocker(mocker):
    mocker.patch(
        "cab_common_auth.decorators.keycloak.introspect",
        return_value={"active": True, "preferred_username": "publisher_test",
                      "username": "publisher_test", "entitiesId": "Railway"},
    )


@pytest.fixture
def railway_use_case(client):
    with client.application.app_context():
        from flask import current_app

        db.session.add(UseCaseModel(name="Railway", event_manager_class="RailwayEventManager",
                                    metadata_schema_class="MetadataSchemaRailway"))
        db.session.commit()
        load_usecases_db(current_app.use_case_factory)


def post(client, payload):
    return client.post("/api/v1/events", headers=HEADERS, json=payload)


def with_data(payload, **changes):
    return {**payload, "data": {**payload["data"], **changes}}


@pytest.mark.usefixtures("railway_use_case", "railway_auth_mocker", "mock_of_create_cards_request")
class TestRailwayEvents:
    def test_today_payload_still_accepted(self, client):
        assert post(client, TODAY_EVENT).status_code == 201

    def test_simulator_payload_accepted(self, client):
        response = post(client, SIMULATOR_EVENT)
        assert response.status_code == 201
        data = response.json["data"]
        assert (data["scenario_id"], data["decision_index"], data["run_mode"]) == ("scenario3", 0, "colearning")
        assert (data["timestep"], data["session_id"]) == (16, "4f1c")

    def test_event_without_decision(self, client):
        assert post(client, with_data(SIMULATOR_EVENT, decision_index=None)).status_code == 201

    def test_unknown_run_mode_rejected(self, client):
        assert post(client, with_data(SIMULATOR_EVENT, run_mode="free")).status_code == 422

    def test_unknown_field_still_rejected(self, client):
        assert post(client, with_data(SIMULATOR_EVENT, recommendations=[])).status_code == 422
