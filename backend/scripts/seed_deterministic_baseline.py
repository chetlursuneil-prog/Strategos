import os
import sys
import uuid
import json
import asyncio
from pathlib import Path
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import insert, select, delete
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.base import Base
from app.db import models as m

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./strategos_dev.db")
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def parse_uuid_env(name: str):
    val = os.getenv(name)
    if not val:
        return None
    try:
        return uuid.UUID(val)
    except Exception:
        return None


async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        tenant_id = parse_uuid_env("SEED_TENANT_ID")
        model_version_id = parse_uuid_env("SEED_MODEL_VERSION_ID")

        if tenant_id is None:
            existing_tenant_id = (await conn.execute(select(m.Tenant.id).limit(1))).scalars().first()
            if existing_tenant_id is None:
                tenant_id = uuid.uuid4()
                await conn.execute(insert(m.Tenant).values(id=tenant_id, name="strategos-baseline-tenant"))
            else:
                tenant_id = existing_tenant_id

        if model_version_id is None:
            existing_mv_id = (
                await conn.execute(
                    select(m.ModelVersion.id).where(m.ModelVersion.tenant_id == tenant_id).limit(1)
                )
            ).scalars().first()
            if existing_mv_id is None:
                model_version_id = uuid.uuid4()
                await conn.execute(
                    insert(m.ModelVersion).values(
                        id=model_version_id,
                        tenant_id=tenant_id,
                        name="strategos-baseline-v1",
                        description="Seeded deterministic baseline",
                        is_active=True,
                    )
                )
            else:
                model_version_id = existing_mv_id

        # Clean previous seeded entities for this model version / tenant
        rule_rows = (await conn.execute(select(m.Rule.id).where(m.Rule.model_version_id == model_version_id))).scalars().all()
        if rule_rows:
            await conn.execute(delete(m.RuleCondition).where(m.RuleCondition.rule_id.in_(rule_rows)))
            await conn.execute(delete(m.RuleImpact).where(m.RuleImpact.rule_id.in_(rule_rows)))
            await conn.execute(delete(m.Rule).where(m.Rule.id.in_(rule_rows)))

        await conn.execute(delete(m.Coefficient).where(m.Coefficient.model_version_id == model_version_id))
        await conn.execute(delete(m.Metric).where(m.Metric.model_version_id == model_version_id))

        sd_rows = (await conn.execute(select(m.StateDefinition.id).where(m.StateDefinition.tenant_id == tenant_id))).scalars().all()
        if sd_rows:
            await conn.execute(delete(m.StateThreshold).where(m.StateThreshold.state_definition_id.in_(sd_rows)))
            await conn.execute(delete(m.StateDefinition).where(m.StateDefinition.id.in_(sd_rows)))

        rt_rows = (await conn.execute(select(m.RestructuringTemplate.id).where(m.RestructuringTemplate.tenant_id == tenant_id))).scalars().all()
        if rt_rows:
            await conn.execute(delete(m.RestructuringRule).where(m.RestructuringRule.template_id.in_(rt_rows)))
            await conn.execute(delete(m.RestructuringTemplate).where(m.RestructuringTemplate.id.in_(rt_rows)))

        # Metrics
        metric_ids = {name: uuid.uuid4() for name in ["revenue", "cost", "margin", "technical_debt"]}
        for name, mid in metric_ids.items():
            await conn.execute(
                insert(m.Metric).values(
                    id=mid,
                    tenant_id=tenant_id,
                    model_version_id=model_version_id,
                    name=name,
                    is_active=True,
                )
            )

        # Coefficients: scalar + formula
        coeffs = [
            ("revenue", "0.08"),
            ("cost", "-0.05"),
            ("margin", "0.40"),
            ("composite_stress", "(cost * 0.04) + (technical_debt * 0.06) - (margin * 0.15)"),
        ]
        for cname, cvalue in coeffs:
            await conn.execute(
                insert(m.Coefficient).values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    model_version_id=model_version_id,
                    name=cname,
                    value=cvalue,
                    is_active=True,
                )
            )

        # Rules
        rules = {
            "high_cost_pressure": {
                "expr": "cost > 220",
                "impact": "12",
                "desc": "Operating cost pressure above tolerance",
            },
            "margin_collapse": {
                "expr": "margin < 0.12",
                "impact": "16",
                "desc": "Margin collapse risk",
            },
            "debt_spike": {
                "expr": "technical_debt > 70",
                "impact": "10",
                "desc": "Technical debt exposure high",
            },
            "revenue_erosion": {
                "expr": "revenue < 900",
                "impact": "9",
                "desc": "Revenue baseline has fallen below expected operating floor",
            },
            "cost_revenue_imbalance": {
                "expr": "cost > (revenue * 0.78)",
                "impact": "11",
                "desc": "Operating cost-to-revenue ratio indicates structural inefficiency",
            },
            "margin_debt_double_stress": {
                "expr": "(margin < 0.15) and (technical_debt > 55)",
                "impact": "14",
                "desc": "Weak margin combined with elevated technical debt increases fragility",
            },
            "margin_cost_stress": {
                "expr": "(margin < 0.18) and (cost > 180)",
                "impact": "8",
                "desc": "Subscale margin with high operating cost raises execution risk",
            },
        }

        for rname, cfg in rules.items():
            rid = uuid.uuid4()
            await conn.execute(
                insert(m.Rule).values(
                    id=rid,
                    tenant_id=tenant_id,
                    model_version_id=model_version_id,
                    name=rname,
                    description=cfg["desc"],
                    is_active=True,
                )
            )
            await conn.execute(
                insert(m.RuleCondition).values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    rule_id=rid,
                    expression=cfg["expr"],
                    is_active=True,
                )
            )
            await conn.execute(
                insert(m.RuleImpact).values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    rule_id=rid,
                    impact=cfg["impact"],
                    is_active=True,
                )
            )

        # States and thresholds
        state_map = {
            "NORMAL": 0,
            "ELEVATED_RISK": 35,
            "CRITICAL_ZONE": 60,
        }
        for sname, threshold in state_map.items():
            sid = uuid.uuid4()
            await conn.execute(
                insert(m.StateDefinition).values(
                    id=sid,
                    tenant_id=tenant_id,
                    name=sname,
                    description=f"Seeded state: {sname}",
                )
            )
            await conn.execute(
                insert(m.StateThreshold).values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    state_definition_id=sid,
                    threshold=str(threshold),
                )
            )

        # Restructuring templates + rules (used in CRITICAL_ZONE)
        templates = [
            {
                "name": "portfolio_rationalization",
                "payload": {"action": "rationalize_portfolio", "owner": "Transformation Office", "horizon_days": 90},
            },
            {
                "name": "cost_containment_program",
                "payload": {"action": "cost_containment", "owner": "CFO", "horizon_days": 60},
            },
        ]

        for t in templates:
            tid = uuid.uuid4()
            await conn.execute(
                insert(m.RestructuringTemplate).values(
                    id=tid,
                    tenant_id=tenant_id,
                    name=t["name"],
                    payload=json.dumps(t["payload"]),
                )
            )
            await conn.execute(
                insert(m.RestructuringRule).values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    template_id=tid,
                )
            )

    await engine.dispose()
    print(f"SEED_TENANT_ID={tenant_id}")
    print(f"SEED_MODEL_VERSION_ID={model_version_id}")
    print("SEED_STATUS=OK")


if __name__ == "__main__":
    asyncio.run(main())
