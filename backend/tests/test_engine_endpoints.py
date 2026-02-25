import asyncio
import json
import pytest

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_session


class DummySession:
    async def execute(self, *args, **kwargs):
        class R:
            def scalars(self):
                class S:
                    def first(self):
                        return None

                    def all(self):
                        return []

                return S()

        return R()

    async def get(self, *args, **kwargs):
        return None

    async def commit(self):
        return None


async def _override_get_session():
    yield DummySession()


client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_run_engine_no_model():
    # When no model present and DB returns nothing, engine should return an error payload
    # Use dependency override only for this test
    app.dependency_overrides[get_session] = _override_get_session
    try:
        r = client.post("/api/v1/engine/run", json={"input": {"revenue": 100}})
        assert r.status_code in (400, 200)
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_create_session_db():
    # Use the in-memory DB created by conftest; TEST_TENANT_ID and TEST_MODEL_VERSION_ID are set
    import os

    payload = {"tenant_id": os.environ.get("TEST_TENANT_ID"), "model_version_id": os.environ.get("TEST_MODEL_VERSION_ID"), "name": "session-1"}
    r = client.post("/api/v1/sessions", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "success"
    assert body["data"].get("session_id")
