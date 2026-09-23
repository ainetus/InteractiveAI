"""Smoke test: post a context, stub out the RL agent, expect an ontology recommendation back."""
import json

POWERGRID_BEARER_TOKEN = "dummy-token-see-PowerGrid_auth_mocker-fixture"


def test_pipeline_smoke_context_to_recommendation(
    client, create_usecases, PowerGrid_auth_mocker, mocker
):
    mocker.patch(
        "resources.PowerGrid.manager.PowerGridManager._get_rl_parades",
        return_value=[],
    )

    with open("tests/tests_resources/rte_recommendation.json") as json_file:
        payload = json.load(json_file)

    headers = {"Authorization": f"Bearer {POWERGRID_BEARER_TOKEN}"}
    response = client.post(
        "/api/v1/recommendation?use_case=PowerGrid",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 200
    recommendations = response.get_json()
    assert isinstance(recommendations, list) and len(recommendations) >= 1

    for reco in recommendations:
        assert reco["use_case"] == "PowerGrid"
        assert reco["agent_type"] in {"IA", "onto"}
        assert reco["title"]
        assert "kpis" in reco

    onto_recos = [r for r in recommendations if r["agent_type"] == "onto"]
    assert onto_recos
    assert any(
        "efficiency_of_the_reco" in (r["kpis"] or {}) for r in onto_recos
    )
