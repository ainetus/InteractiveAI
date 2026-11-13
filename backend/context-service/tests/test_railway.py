"""Railway contexts: the snapshot of the scripted simulator (usecases_examples/Railway/) and
today's GPS contexts are both accepted; unknown fields are still rejected."""

import pytest

from api.models import UseCaseModel, db
from api.utils import load_usecases_db

HEADERS = {"Authorization": "Bearer railway-test-token"}

TODAY_CONTEXT = {
    "use_case": "Railway",
    "date": "2026-11-20T09:00:00+00:00",
    "data": {"trains": [{"id_train": "AB001", "nb_passengers_onboard": 468,
                         "latitude": 46.58, "longitude": 0.33, "failure": True}]},
}

SIMULATOR_CONTEXT = {
    "use_case": "Railway",
    "date": "2026-11-20T09:00:16+00:00",
    "data": {
        "trains": [{"id_train": "Train_0", "name": "G 3", "position": [7, 9], "direction": 1,
                    "done": False, "failure": False, "planned_departure": 1,
                    "planned_arrival": 40, "actual_departure": 1, "actual_arrival": None,
                    "delay": 0, "route": [[7, 2], [7, 3]]}],
        "session": {"session_id": "4f1c",
                    "scenario_order": [{"scenario_id": "scenario3", "mode": "colearning"}],
                    "scenario_position": 0,
                    "started_at": "2026-11-20T08:59:00+00:00", "ended_at": None},
        "scenario": {"id": "scenario3", "name": "Szenario 3 — Güterverkehr vs Personenverkehr",
                     "mode": "colearning", "step": 16, "state": "paused_for_decision",
                     "decision_open": True},
        "infra": {"map": "maps/map3.json", "rows": 15, "cols": 20, "grid": [[0, 0]],
                  "stations": [{"id": 1, "r": 7, "c": 17, "name": "Station 1"}],
                  "marey_link": {"start": [7, 1], "end": [7, 18]},
                  "marey_mapping": {"7,2": 1, "7,3": 2},
                  "planned_paths": {"Train_0": [[1, 1], [3, 2]]},
                  "link_map": {"grid": [[1025]], "mapping": [[[7, 2], [1, 1]]], "levels": []}},
        "history": [{"0": {"position": [7, 2], "direction": 1, "moving": True,
                           "target": [7, 17], "done": False}}],
        "decisions": [],
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

        db.session.add(UseCaseModel(name="Railway", context_manager_class="RailwayContextManager",
                                    metadata_schema_class="MetadataSchemaRailway"))
        db.session.commit()
        load_usecases_db(current_app.use_case_factory)


def post(client, payload):
    return client.post("/api/v1/contexts", headers=HEADERS, json=payload)


@pytest.mark.usefixtures("railway_use_case", "railway_auth_mocker")
class TestRailwayContexts:
    def test_today_payload_still_accepted(self, client):
        assert post(client, TODAY_CONTEXT).status_code == 201

    def test_simulator_payload_accepted_and_returned(self, client):
        assert post(client, SIMULATOR_CONTEXT).status_code == 201
        response = client.get("/api/v1/contexts?use_case=Railway", headers=HEADERS)
        assert response.status_code == 200
        data = response.json[0]["data"]
        assert data["scenario"]["state"] == "paused_for_decision"
        assert data["infra"]["marey_mapping"] == {"7,2": 1, "7,3": 2}
        assert data["session"]["scenario_order"][0] == {"scenario_id": "scenario3", "mode": "colearning"}

    def test_unknown_field_still_rejected(self, client):
        payload = {**SIMULATOR_CONTEXT, "data": {**SIMULATOR_CONTEXT["data"], "render": "x.png"}}
        assert post(client, payload).status_code == 422
