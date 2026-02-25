import os
import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import models
from app.db.session import AsyncSessionLocal


client = TestClient(app)


def test_engine_run_writes_audit_log():
    tenant_id = os.environ.get("TEST_TENANT_ID")
    model_version_id = os.environ.get("TEST_MODEL_VERSION_ID")
    assert tenant_id and model_version_id

    resp = client.post(
        "/api/v1/engine/run",
        json={
            "tenant_id": tenant_id,
            "model_version_id": model_version_id,
            "input": {"revenue": 1000, "margin": 0.1},
        },
    )
    assert resp.status_code == 200

    async def _count():
        async with AsyncSessionLocal() as db:
            q = select(models.AuditLog).where(models.AuditLog.action == "ENGINE_RUN")
            res = await db.execute(q)
            rows = res.scalars().all()
            return len(rows)

    count = asyncio.run(_count())
    assert count >= 1
