import os

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_openclaw_skill_contract_flow():
    tenant_id = os.environ.get("TEST_TENANT_ID")
    model_version_id = os.environ.get("TEST_MODEL_VERSION_ID")
    assert tenant_id and model_version_id

    # Ensure at least one rule exists for /show_rules
    create_rule = client.post(
        "/api/v1/rules",
        json={
            "tenant_id": tenant_id,
            "model_version_id": model_version_id,
            "name": "OpenClaw Rule",
            "description": "Rule for skills endpoint",
        },
    )
    assert create_rule.status_code == 200
    rule_id = create_rule.json()["data"]["rule_id"]

    cond = client.post(
        f"/api/v1/rules/{rule_id}/conditions",
        json={"tenant_id": tenant_id, "expression": "revenue < 1200"},
    )
    assert cond.status_code == 200

    impact = client.post(
        f"/api/v1/rules/{rule_id}/impacts",
        json={"tenant_id": tenant_id, "impact": "1.2"},
    )
    assert impact.status_code == 200

    # 1) Create session through skill endpoint
    create_session = client.post(
        "/api/v1/advisory/skills/create_session",
        json={"tenant_id": tenant_id, "model_version_id": model_version_id, "name": "oc-session"},
    )
    assert create_session.status_code == 200
    session_id = create_session.json()["data"]["session_id"]

    # 2) Run engine through skill endpoint
    run_engine = client.post(
        "/api/v1/advisory/skills/run_engine",
        json={
            "tenant_id": tenant_id,
            "model_version_id": model_version_id,
            "session_id": session_id,
            "input": {"revenue": 1000, "margin": 0.2},
        },
    )
    assert run_engine.status_code == 200
    run_data = run_engine.json()["data"]
    assert run_data.get("snapshot")

    # 3) Fetch state
    state_resp = client.get(f"/api/v1/advisory/skills/state/{session_id}")
    assert state_resp.status_code == 200
    assert "state" in state_resp.json()["data"]

    # 4) Fetch contributions
    contrib_resp = client.get(f"/api/v1/advisory/skills/contributions/{session_id}")
    assert contrib_resp.status_code == 200
    assert isinstance(contrib_resp.json()["data"].get("contributions"), list)

    # 5) Fetch restructuring details
    restruct_resp = client.get(f"/api/v1/advisory/skills/restructuring/{session_id}")
    assert restruct_resp.status_code == 200
    assert "restructuring_actions" in restruct_resp.json()["data"]

    # 6) List model versions via skill endpoint
    mv_resp = client.get(f"/api/v1/advisory/skills/model_versions?tenant_id={tenant_id}")
    assert mv_resp.status_code == 200
    assert isinstance(mv_resp.json()["data"].get("model_versions"), list)

    # 7) Show rules via developer command endpoint
    show_rules = client.get(f"/api/v1/advisory/skills/show_rules?model_version_id={model_version_id}")
    assert show_rules.status_code == 200
    rules_data = show_rules.json()["data"].get("rules")
    assert isinstance(rules_data, list)
    assert len(rules_data) >= 1
