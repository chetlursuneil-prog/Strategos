import os
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_model_versions_create_list_activate():
    tenant_id = os.environ.get("TEST_TENANT_ID")

    create_resp = client.post(
        "/api/v1/models/versions",
        json={"tenant_id": tenant_id, "name": "mv-next", "description": "next version", "is_active": False},
    )
    assert create_resp.status_code == 200
    mv_id = create_resp.json()["data"]["model_version_id"]

    list_resp = client.get(f"/api/v1/models/versions?tenant_id={tenant_id}")
    assert list_resp.status_code == 200
    model_versions = list_resp.json()["data"]["model_versions"]
    assert any(item["id"] == mv_id for item in model_versions)

    activate_resp = client.patch(f"/api/v1/models/versions/{mv_id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["data"]["is_active"] is True


def test_states_and_thresholds_flow():
    tenant_id = os.environ.get("TEST_TENANT_ID")

    state_resp = client.post(
        "/api/v1/states",
        json={"tenant_id": tenant_id, "name": "ELEVATED_RISK", "description": "Risk state"},
    )
    assert state_resp.status_code == 200
    state_id = state_resp.json()["data"]["state_definition_id"]

    threshold_resp = client.post(
        f"/api/v1/states/{state_id}/thresholds",
        json={"tenant_id": tenant_id, "threshold": "2"},
    )
    assert threshold_resp.status_code == 200
    assert threshold_resp.json()["data"]["state_threshold_id"]

    list_state_resp = client.get(f"/api/v1/states?tenant_id={tenant_id}")
    assert list_state_resp.status_code == 200
    assert any(item["id"] == state_id for item in list_state_resp.json()["data"]["states"])

    list_threshold_resp = client.get(f"/api/v1/states/{state_id}/thresholds")
    assert list_threshold_resp.status_code == 200
    thresholds = list_threshold_resp.json()["data"]["thresholds"]
    assert any(item["threshold"] == "2" for item in thresholds)
