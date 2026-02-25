import os
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.main import app
from app.db import models
from app.db.session import AsyncSessionLocal


client = TestClient(app)


def test_engine_score_breakdown_and_restructuring_trigger():
    tenant_id = os.environ.get("TEST_TENANT_ID")
    model_version_id = os.environ.get("TEST_MODEL_VERSION_ID")
    assert tenant_id and model_version_id

    # Seed coefficient + rule + condition + impact + CRITICAL threshold + restructuring template/rule
    async def _seed():
        async with AsyncSessionLocal() as db:
            rule_id = uuid.uuid4()
            state_id = uuid.uuid4()
            template_id = uuid.uuid4()

            await db.execute(
                insert(models.Coefficient).values(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    model_version_id=uuid.UUID(model_version_id),
                    name="revenue",
                    value="0.02",
                    is_active=True,
                )
            )

            await db.execute(
                insert(models.Rule).values(
                    id=rule_id,
                    tenant_id=uuid.UUID(tenant_id),
                    model_version_id=uuid.UUID(model_version_id),
                    name="Low revenue",
                    description="Revenue below threshold",
                    is_active=True,
                )
            )

            await db.execute(
                insert(models.RuleCondition).values(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    rule_id=rule_id,
                    expression="revenue < 1000",
                    is_active=True,
                )
            )

            await db.execute(
                insert(models.RuleImpact).values(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    rule_id=rule_id,
                    impact="3.5",
                    is_active=True,
                )
            )

            await db.execute(
                insert(models.StateDefinition).values(
                    id=state_id,
                    tenant_id=uuid.UUID(tenant_id),
                    name="CRITICAL_ZONE",
                    description="Critical",
                )
            )

            # Make CRITICAL_ZONE easy to trigger via total_score >= 1
            await db.execute(
                insert(models.StateThreshold).values(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    state_definition_id=state_id,
                    threshold="1",
                )
            )

            await db.execute(
                insert(models.RestructuringTemplate).values(
                    id=template_id,
                    tenant_id=uuid.UUID(tenant_id),
                    name="Emergency Plan",
                    payload='{"action":"cost_reduction","priority":"high"}',
                )
            )

            await db.execute(
                insert(models.RestructuringRule).values(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    template_id=template_id,
                )
            )

            await db.commit()

    import asyncio

    asyncio.run(_seed())

    resp = client.post(
        "/api/v1/engine/run",
        json={"model_version_id": model_version_id, "input": {"revenue": 900}},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["state"] == "CRITICAL_ZONE"
    assert isinstance(body.get("score_breakdown"), dict)
    assert body["score_breakdown"].get("total_score", 0) >= 1
    assert isinstance(body.get("restructuring_actions"), list)
    assert len(body["restructuring_actions"]) >= 1
