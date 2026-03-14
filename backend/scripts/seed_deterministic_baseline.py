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
        metric_names = [
            "revenue",
            "cost",
            "margin",
            "technical_debt",
            "revenue_growth_yoy_pct",
            "customer_churn_pct",
            "net_promoter_score",
            "cloud_adoption_pct",
            "release_frequency_per_month",
            "lead_time_days",
            "change_failure_rate_pct",
            "p1_incidents_per_month",
            "automation_coverage_pct",
            "cyber_findings_open_high",
            "regulatory_findings_open",
            "critical_role_attrition_pct",
            "vendor_concentration_pct",
            "top_customer_concentration_pct",
            "digital_capex_pct_of_revenue",
            "cash_conversion_cycle_days",
        ]
        metric_ids = {name: uuid.uuid4() for name in metric_names}
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

        # Coefficients: formula-first so partial input can still produce a
        # nuanced baseline once defaults are applied in intake.
        coeffs = [
            ("scale_protection", "revenue * 0.01"),
            ("operating_drag", "-(cost * 0.012)"),
            ("profitability_buffer", "margin * 140"),
            ("tech_debt_drag", "-(technical_debt * 0.18)"),
            ("growth_signal", "revenue_growth_yoy_pct * 0.8"),
            ("churn_drag", "-(customer_churn_pct * 3.0)"),
            ("experience_signal", "net_promoter_score * 0.2"),
            ("delivery_velocity", "release_frequency_per_month * 0.5"),
            ("lead_time_drag", "-(lead_time_days * 0.4)"),
            ("change_failure_drag", "-(change_failure_rate_pct * 0.35)"),
            ("reliability_drag", "-(p1_incidents_per_month * 1.5)"),
            ("automation_signal", "automation_coverage_pct * 0.1"),
            ("compliance_drag", "-((cyber_findings_open_high * 1.2) + (regulatory_findings_open * 1.5))"),
            ("attrition_drag", "-(critical_role_attrition_pct * 0.5)"),
            ("concentration_drag", "-((vendor_concentration_pct * 0.08) + (top_customer_concentration_pct * 0.1))"),
            ("digital_investment_signal", "digital_capex_pct_of_revenue * 0.7"),
            ("liquidity_drag", "-(cash_conversion_cycle_days * 0.12)"),
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
            "margin_collapse_risk": {
                "expr": "margin < 0.12",
                "impact": "16",
                "desc": "Margin collapse risk",
            },
            "technical_debt_overhang": {
                "expr": "technical_debt > 65",
                "impact": "12",
                "desc": "Technical debt exposure above safe modernization range",
            },
            "structural_cost_intensity": {
                "expr": "cost > (revenue * 0.82)",
                "impact": "14",
                "desc": "Cost-to-revenue ratio indicates structural inefficiency",
            },
            "growth_deceleration": {
                "expr": "revenue_growth_yoy_pct < 3",
                "impact": "8",
                "desc": "Revenue growth has slowed below strategic expectation",
            },
            "customer_retention_pressure": {
                "expr": "customer_churn_pct > 2.8",
                "impact": "9",
                "desc": "Customer churn pressure threatens durable growth",
            },
            "delivery_instability": {
                "expr": "(lead_time_days > 14) or (change_failure_rate_pct > 20)",
                "impact": "8",
                "desc": "Delivery system instability increases transformation execution risk",
            },
            "operational_reliability_breach": {
                "expr": "p1_incidents_per_month > 5",
                "impact": "10",
                "desc": "High-severity incident load indicates fragile operations",
            },
            "compliance_security_pressure": {
                "expr": "(cyber_findings_open_high > 10) or (regulatory_findings_open > 5)",
                "impact": "11",
                "desc": "Compliance and security findings exceed tolerance",
            },
            "critical_talent_loss": {
                "expr": "critical_role_attrition_pct > 12",
                "impact": "7",
                "desc": "Critical-role attrition threatens execution continuity",
            },
            "concentration_exposure": {
                "expr": "(vendor_concentration_pct > 50) or (top_customer_concentration_pct > 40)",
                "impact": "8",
                "desc": "Concentration risk increases dependency fragility",
            },
            "modernization_gap": {
                "expr": "(cloud_adoption_pct < 40) and (automation_coverage_pct < 40)",
                "impact": "9",
                "desc": "Modernization base is below minimum viable transformation readiness",
            },
            "cash_cycle_stress": {
                "expr": "cash_conversion_cycle_days > 80",
                "impact": "8",
                "desc": "Cash conversion cycle is too long for resilient execution",
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
            "ELEVATED_RISK": 40,
            "CRITICAL_ZONE": 90,
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
            {
                "name": "technology_modernization_wave",
                "payload": {"action": "modernization_wave", "owner": "CTO", "horizon_days": 120},
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
