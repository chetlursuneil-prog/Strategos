import os
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_rules_crud_flow():
    tenant_id = os.environ.get("TEST_TENANT_ID")
    model_version_id = os.environ.get("TEST_MODEL_VERSION_ID")

    # create rule
    create_payload = {
        "tenant_id": tenant_id,
        "model_version_id": model_version_id,
        "name": "Revenue Risk Rule",
        "description": "Detect low revenue",
    }
    create_resp = client.post("/api/v1/rules", json=create_payload)
    assert create_resp.status_code == 200
    rule_id = create_resp.json()["data"]["rule_id"]
    assert rule_id

    # add condition
    cond_resp = client.post(
        f"/api/v1/rules/{rule_id}/conditions",
        json={"tenant_id": tenant_id, "expression": "revenue < 1000"},
    )
    assert cond_resp.status_code == 200
    assert cond_resp.json()["data"]["condition_id"]

    # add impact
    impact_resp = client.post(
        f"/api/v1/rules/{rule_id}/impacts",
        json={"tenant_id": tenant_id, "impact": "2.5"},
    )
    assert impact_resp.status_code == 200
    assert impact_resp.json()["data"]["impact_id"]

    # list by model version
    list_resp = client.get(f"/api/v1/rules?model_version_id={model_version_id}")
    assert list_resp.status_code == 200
    rules = list_resp.json()["data"]["rules"]
    assert any(item["id"] == rule_id for item in rules)

    # deactivate
    deactivate_resp = client.patch(f"/api/v1/rules/{rule_id}/deactivate")
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["data"]["is_active"] is False
