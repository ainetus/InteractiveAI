"""End-to-end smoke test of the PowerGrid recommendation pipeline.

There is no local RL agent service in this repo — PowerGrid recommendations
combine an *external* RL agent API (best-effort, network-dependent) with the
ontology recommender that ships in this service. This test isolates the part
that must always work offline: post a context/event exactly as the simulator
serializes it, go through the real Flask view + auth + use-case dispatch, and
get back at least one well-formed ontology recommendation. The RL agent call
is stubbed out so the test doesn't depend on network access to the external
service.
"""
import json

POWERGRID_BEARER_TOKEN = "dummy-token-see-PowerGrid_auth_mocker-fixture"


def test_pipeline_smoke_context_to_recommendation(
    client, create_usecases, PowerGrid_auth_mocker, mocker
):
    """Post a simulator-shaped context and get an actionable ontology recommendation back."""
    # No local/reachable RL agent in this environment — stub it out so the
    # pipeline is exercised deterministically, offline, end to end.
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

    # Every recommendation is well-formed and tagged with its source.
    for reco in recommendations:
        assert reco["use_case"] == "PowerGrid"
        assert reco["agent_type"] in {"IA", "onto"}
        assert reco["title"]
        assert "kpis" in reco

    # With the RL agent stubbed out, only the ontology recommender can have
    # answered — confirm the pipeline actually produced one (not just the
    # "no recommendation found" default), with an efficiency KPI attached.
    onto_recos = [r for r in recommendations if r["agent_type"] == "onto"]
    assert onto_recos
    assert any(
        "efficiency_of_the_reco" in (r["kpis"] or {}) for r in onto_recos
    )
