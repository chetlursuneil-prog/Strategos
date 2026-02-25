import os

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_session_snapshot_versioning_and_replay():
    tenant_id = os.environ.get("TEST_TENANT_ID")
    model_version_id = os.environ.get("TEST_MODEL_VERSION_ID")
    assert tenant_id and model_version_id

    # Create session
    create_resp = client.post(
        "/api/v1/sessions",
        json={"tenant_id": tenant_id, "model_version_id": model_version_id, "name": "replay-session"},
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["data"]["session_id"]

    # Run engine twice with same session
    run1 = client.post(
        "/api/v1/engine/run",
        json={"tenant_id": tenant_id, "model_version_id": model_version_id, "session_id": session_id, "input": {"revenue": 1100}},
    )
    assert run1.status_code == 200

    run2 = client.post(
        "/api/v1/engine/run",
        json={"tenant_id": tenant_id, "model_version_id": model_version_id, "session_id": session_id, "input": {"revenue": 900}},
    )
    assert run2.status_code == 200

    # Fetch snapshots
    snapshots_resp = client.get(f"/api/v1/sessions/{session_id}/snapshots")
    assert snapshots_resp.status_code == 200
    snapshots = snapshots_resp.json()["data"]
    assert int(snapshots.get("version", 0)) >= 2
    assert isinstance(snapshots.get("history"), list)
    assert len(snapshots["history"]) >= 2

    # Replay audit events
    replay_resp = client.get(f"/api/v1/sessions/{session_id}/replay")
    assert replay_resp.status_code == 200
    replay = replay_resp.json()["data"]
    assert replay.get("event_count", 0) >= 2
    assert isinstance(replay.get("events"), list)

    first_event = replay["events"][0]
    audit_log_id = first_event["audit_log_id"]

    single_replay = client.get(f"/api/v1/sessions/replay/audit/{audit_log_id}")
    assert single_replay.status_code == 200
    payload = single_replay.json()["data"]
    assert payload["audit_log_id"] == audit_log_id
    assert payload["action"] == "ENGINE_RUN"
    # replay snapshot may contain deterministic error only if config missing
    assert "replay_snapshot" in payload
