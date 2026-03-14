"""Natural Language Intake endpoint.

Accepts plain-English enterprise descriptions, extracts structured metrics
via regex/keyword extraction, creates a session, runs the deterministic
engine, and returns the full snapshot with an auto-generated advisory summary.

When OpenClaw integration is live the extraction can be delegated to the
schema-extraction agent; this module provides a deterministic fallback that
works without any external LLM dependency.
"""

import re
import uuid
import json
from typing import Dict, Any, Optional, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import format_response
from app.db import models
from app.db.session import get_session
from app.services.engine import run_deterministic_engine

router = APIRouter()


# ── Extraction patterns ─────────────────────────────────────────────────
# Each pattern maps to a metric name and a normaliser.

_PATTERNS: List[Tuple[str, str, float]] = [
    # revenue / cost are normalized to millions
    (r"(?:\$\s*)?([\d,.]+)\s*(?:bn|billion|b)\b(?:[^\.\n]{0,40})?(?:revenue|turnover|sales)", "revenue", 1000.0),
    (r"(?:\$\s*)?([\d,.]+)\s*(?:m|million)\b(?:[^\.\n]{0,40})?(?:revenue|turnover|sales)", "revenue", 1.0),
    (r"(?:revenue|turnover|sales)\s*(?:of|at|around|≈|~|is|=|:)?\s*\$?\s*([\d,.]+)\s*(bn|billion|b|m|million)?", "revenue", 1.0),

    (r"(?:\$\s*)?([\d,.]+)\s*(?:bn|billion|b)\b(?:[^\.\n]{0,40})?(?:cost|opex|expenditure|capex)", "cost", 1000.0),
    (r"(?:\$\s*)?([\d,.]+)\s*(?:m|million)\b(?:[^\.\n]{0,40})?(?:cost|opex|expenditure|capex)", "cost", 1.0),
    (r"(?:cost|opex|expenditure|capex|operating\s+costs?)\s*(?:of|at|around|≈|~|is|=|:)?\s*\$?\s*([\d,.]+)\s*(bn|billion|b|m|million)?", "cost", 1.0),

    # profitability / debt
    (r"([\d,.]+)\s*%\s*(?:margin|ebitda|operating\s+margin)", "margin", 0.01),
    (r"(?:margin|ebitda)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "margin", 0.01),
    (r"(?:margin|ebitda)\s*(?:of|at|around|≈|~|is|=|:)?\s*(0\.\d+)", "margin", 1.0),

    (r"(?:technical?\s*d(?:ebt|et)|tech\s*d(?:ebt|et)|legacy\s*d(?:ebt|et))\s*(?:of|at|around|≈|~|score|is|=|:)?\s*([\d,.]+)\s*%?", "technical_debt", 1.0),
    (r"([\d,.]+)\s*%?\s*(?:technical?\s*d(?:ebt|et)|tech\s*d(?:ebt|et)|legacy\s*d(?:ebt|et))", "technical_debt", 1.0),

    # growth / customer / ops / governance
    (r"(?:revenue\s+growth|growth|yoy\s+growth)\s*(?:of|at|around|≈|~|is|=|:)?\s*([-\d,.]+)\s*%", "revenue_growth_yoy_pct", 1.0),
    (r"([-\d,.]+)\s*%\s*(?:revenue\s+growth|growth)", "revenue_growth_yoy_pct", 1.0),
    (r"(?:churn|customer\s+churn)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "customer_churn_pct", 1.0),
    (r"(?:nps|net\s+promoter\s+score)\s*(?:of|at|around|≈|~|is|=|:)?\s*([-\d,.]+)", "net_promoter_score", 1.0),
    (r"(?:cloud\s+adoption)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "cloud_adoption_pct", 1.0),
    (r"(?:release\s+frequency)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "release_frequency_per_month", 1.0),
    (r"(?:lead\s*time|lead\s*time\s*days)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "lead_time_days", 1.0),
    (r"(?:change\s+failure\s+rate)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "change_failure_rate_pct", 1.0),
    (r"(?:p1\s+incidents?)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "p1_incidents_per_month", 1.0),
    (r"(?:automation\s+coverage)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "automation_coverage_pct", 1.0),
    (r"(?:high\s+cyber\s+findings|cyber\s+findings)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "cyber_findings_open_high", 1.0),
    (r"(?:regulatory\s+findings)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "regulatory_findings_open", 1.0),
    (r"(?:critical\s+role\s+attrition|attrition)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "critical_role_attrition_pct", 1.0),
    (r"(?:vendor\s+concentration)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "vendor_concentration_pct", 1.0),
    (r"(?:top\s+customer\s+concentration|customer\s+concentration)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)\s*%", "top_customer_concentration_pct", 1.0),
    (r"(?:digital\s+capex(?:\s+as\s+)?(?:%|percent)\s+of\s+revenue)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "digital_capex_pct_of_revenue", 1.0),
    (r"(?:cash\s+conversion\s+cycle)\s*(?:of|at|around|≈|~|is|=|:)?\s*([\d,.]+)", "cash_conversion_cycle_days", 1.0),
]

_PROFILE_DEFAULTS: Dict[str, Dict[str, float]] = {
    "balanced": {
        "revenue": 1200.0,
        "cost": 780.0,
        "margin": 0.18,
        "technical_debt": 45.0,
        "revenue_growth_yoy_pct": 8.0,
        "customer_churn_pct": 1.8,
        "net_promoter_score": 35.0,
        "cloud_adoption_pct": 55.0,
        "release_frequency_per_month": 8.0,
        "lead_time_days": 7.0,
        "change_failure_rate_pct": 12.0,
        "p1_incidents_per_month": 2.0,
        "automation_coverage_pct": 55.0,
        "cyber_findings_open_high": 3.0,
        "regulatory_findings_open": 1.0,
        "critical_role_attrition_pct": 8.0,
        "vendor_concentration_pct": 35.0,
        "top_customer_concentration_pct": 28.0,
        "digital_capex_pct_of_revenue": 9.0,
        "cash_conversion_cycle_days": 55.0,
    },
    "growth": {
        "revenue": 1800.0,
        "cost": 1080.0,
        "margin": 0.22,
        "technical_debt": 35.0,
        "revenue_growth_yoy_pct": 14.0,
        "customer_churn_pct": 1.4,
        "net_promoter_score": 45.0,
        "cloud_adoption_pct": 68.0,
        "release_frequency_per_month": 12.0,
        "lead_time_days": 5.0,
        "change_failure_rate_pct": 9.0,
        "p1_incidents_per_month": 1.0,
        "automation_coverage_pct": 65.0,
        "cyber_findings_open_high": 2.0,
        "regulatory_findings_open": 1.0,
        "critical_role_attrition_pct": 7.0,
        "vendor_concentration_pct": 30.0,
        "top_customer_concentration_pct": 24.0,
        "digital_capex_pct_of_revenue": 11.0,
        "cash_conversion_cycle_days": 45.0,
    },
    "stressed": {
        "revenue": 900.0,
        "cost": 760.0,
        "margin": 0.10,
        "technical_debt": 68.0,
        "revenue_growth_yoy_pct": 2.0,
        "customer_churn_pct": 2.9,
        "net_promoter_score": 10.0,
        "cloud_adoption_pct": 38.0,
        "release_frequency_per_month": 4.0,
        "lead_time_days": 15.0,
        "change_failure_rate_pct": 22.0,
        "p1_incidents_per_month": 6.0,
        "automation_coverage_pct": 35.0,
        "cyber_findings_open_high": 11.0,
        "regulatory_findings_open": 6.0,
        "critical_role_attrition_pct": 14.0,
        "vendor_concentration_pct": 52.0,
        "top_customer_concentration_pct": 42.0,
        "digital_capex_pct_of_revenue": 6.0,
        "cash_conversion_cycle_days": 85.0,
    },
}

_PROFILE_ALIASES = {
    "balanced": "balanced",
    "default": "balanced",
    "baseline": "balanced",
    "growth": "growth",
    "optimistic": "growth",
    "aggressive": "growth",
    "stressed": "stressed",
    "conservative": "stressed",
    "risk": "stressed",
    "turnaround": "stressed",
    "none": "none",
    "no_defaults": "none",
    "raw": "none",
}

_STRESSED_HINTS = ["critical", "crisis", "distress", "severe", "high debt", "legacy burden", "declining", "pressure"]
_GROWTH_HINTS = ["high growth", "strong growth", "healthy", "stable", "modern", "scaling", "expanding"]
_NO_DEFAULT_HINTS = ["no defaults", "no assumptions", "raw input only", "as-is"]

_TEXTUAL_OVERRIDES: Dict[str, List[Tuple[str, float]]] = {
    "technical_debt": [
        (r"very\s+high\s+(?:technical\s+)?d(?:ebt|et)|massive\s+tech\s+d(?:ebt|et)|legacy\s+stack|(?:technical\s+|tech\s+)?d(?:ebt|et)\s*(?:is|at|around|:)?\s*very\s+high", 85.0),
        (r"high\s+(?:technical\s+)?d(?:ebt|et)|significant\s+tech\s+d(?:ebt|et)|(?:technical\s+|tech\s+)?d(?:ebt|et)\s*(?:is|at|around|:)?\s*high", 72.0),
        (r"moderate\s+(?:technical\s+)?d(?:ebt|et)|some\s+tech\s+d(?:ebt|et)|(?:technical\s+|tech\s+)?d(?:ebt|et)\s*(?:is|at|around|:)?\s*moderate", 50.0),
        (r"low\s+(?:technical\s+)?d(?:ebt|et)|minimal\s+d(?:ebt|et)|clean\s+stack|(?:technical\s+|tech\s+)?d(?:ebt|et)\s*(?:is|at|around|:)?\s*low", 25.0),
    ],
    "margin": [
        (r"thin\s+margin|wafer[-\s]?thin|barely\s+profitable|break[-\s]?even", 0.07),
        (r"healthy\s+margin|strong\s+margin|high\s+margin", 0.24),
    ],
    "revenue_growth_yoy_pct": [
        (r"declining\s+revenue|negative\s+growth", -3.0),
        (r"strong\s+growth|rapid\s+growth", 14.0),
    ],
    "customer_churn_pct": [
        (r"high\s+churn|rising\s+churn", 3.2),
        (r"low\s+churn|stable\s+retention", 1.4),
    ],
}

_EXPLICIT_LABEL_PATTERNS: List[Tuple[str, str]] = [
    (r"\brevenue\s*[:=]\s*\$?\s*([\d,.]+)\s*(m|million|bn|billion|b)?\b", "revenue"),
    (r"\b(?:operating\s+)?costs?\s*[:=]\s*\$?\s*([\d,.]+)\s*(m|million|bn|billion|b)?\b", "cost"),
    (r"\b(?:margin|operating\s+margin)\s*[:=]\s*([\d,.]+)\s*%?\b", "margin"),
    (r"\b(?:technical\s+debt|tech\s+debt)\s*[:=]\s*([\d,.]+)\s*%?\b", "technical_debt"),
    (r"\b(?:revenue\s+growth|growth|yoy\s+growth)\s*[:=]\s*([-\d,.]+)\s*%?\b", "revenue_growth_yoy_pct"),
    (r"\b(?:customer\s+churn|churn)\s*[:=]\s*([\d,.]+)\s*%?\b", "customer_churn_pct"),
    (r"\b(?:nps|net\s+promoter\s+score)\s*[:=]\s*([-\d,.]+)\b", "net_promoter_score"),
    (r"\bcloud\s+adoption\s*[:=]\s*([\d,.]+)\s*%?\b", "cloud_adoption_pct"),
    (r"\brelease\s+frequency\s*[:=]\s*([\d,.]+)\b", "release_frequency_per_month"),
    (r"\blead\s*time(?:\s*days)?\s*[:=]\s*([\d,.]+)\b", "lead_time_days"),
    (r"\bchange\s+failure\s+rate\s*[:=]\s*([\d,.]+)\s*%?\b", "change_failure_rate_pct"),
    (r"\bp1\s+incidents?\s*[:=]\s*([\d,.]+)\b", "p1_incidents_per_month"),
    (r"\bautomation\s+coverage\s*[:=]\s*([\d,.]+)\s*%?\b", "automation_coverage_pct"),
    (r"\b(?:high\s+)?cyber\s+findings\s*[:=]\s*([\d,.]+)\b", "cyber_findings_open_high"),
    (r"\bregulatory\s+findings\s*[:=]\s*([\d,.]+)\b", "regulatory_findings_open"),
    (r"\b(?:critical\s+role\s+)?attrition\s*[:=]\s*([\d,.]+)\s*%?\b", "critical_role_attrition_pct"),
    (r"\bvendor\s+concentration\s*[:=]\s*([\d,.]+)\s*%?\b", "vendor_concentration_pct"),
    (r"\b(?:top\s+customer\s+)?customer\s+concentration\s*[:=]\s*([\d,.]+)\s*%?\b", "top_customer_concentration_pct"),
    (r"\bdigital\s+capex(?:\s+as\s+%?\s+of\s+revenue)?\s*[:=]\s*([\d,.]+)\s*%?\b", "digital_capex_pct_of_revenue"),
    (r"\bcash\s+conversion\s+cycle\s*[:=]\s*([\d,.]+)\b", "cash_conversion_cycle_days"),
]


def _unit_multiplier(unit: Optional[str]) -> float:
    if not unit:
        return 1.0
    u = unit.lower()
    if u in ("bn", "billion", "b"):
        return 1000.0
    return 1.0


_NON_NEGATIVE_METRICS = {
    "revenue",
    "cost",
    "release_frequency_per_month",
    "lead_time_days",
    "p1_incidents_per_month",
    "cyber_findings_open_high",
    "regulatory_findings_open",
    "cash_conversion_cycle_days",
}

_PERCENT_0_TO_100_METRICS = {
    "technical_debt",
    "customer_churn_pct",
    "cloud_adoption_pct",
    "change_failure_rate_pct",
    "automation_coverage_pct",
    "critical_role_attrition_pct",
    "vendor_concentration_pct",
    "top_customer_concentration_pct",
    "digital_capex_pct_of_revenue",
}


def _resolve_assumption_profile(text: str, requested_profile: Optional[str]) -> str:
    requested = (requested_profile or "").strip().lower()
    if requested in _PROFILE_ALIASES:
        return _PROFILE_ALIASES[requested]
    if requested in _PROFILE_DEFAULTS:
        return requested

    lowered = (text or "").lower()
    if any(h in lowered for h in _NO_DEFAULT_HINTS):
        return "none"
    if any(h in lowered for h in _STRESSED_HINTS):
        return "stressed"
    if any(h in lowered for h in _GROWTH_HINTS):
        return "growth"
    return "balanced"


def _sanitize_metric(metric: str, value: float) -> float:
    n = float(value)

    if metric in _NON_NEGATIVE_METRICS:
        n = max(0.0, n)
    elif metric == "margin":
        if n > 1.0:
            n = n / 100.0
        n = max(-0.50, min(0.80, n))
        return round(n, 4)
    elif metric in _PERCENT_0_TO_100_METRICS:
        n = max(0.0, min(100.0, n))
    elif metric == "net_promoter_score":
        n = max(-100.0, min(100.0, n))
    elif metric == "revenue_growth_yoy_pct":
        n = max(-50.0, min(80.0, n))

    return round(n, 2)


def extract_metrics(text: str, assumption_profile: Optional[str] = None) -> Tuple[Dict[str, float], str, Dict[str, str]]:
    """Deterministic regex extraction with optional profile-based default filling."""
    extracted: Dict[str, float] = {}
    metric_source: Dict[str, str] = {}
    raw_text = text or ""

    # Prefer explicit "Metric: value" blocks first.
    for pattern, metric in _EXPLICIT_LABEL_PATTERNS:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if not match:
            continue

        raw = match.group(1).replace(",", "")
        unit = match.group(2) if len(match.groups()) > 1 else None
        try:
            value = float(raw)
        except ValueError:
            continue

        if metric in ("revenue", "cost"):
            extracted[metric] = value * _unit_multiplier(unit)
        elif metric == "margin":
            extracted[metric] = value / 100.0 if value > 1 else value
        else:
            extracted[metric] = value
        metric_source[metric] = "explicit_input"

    # Then apply natural-language patterns for still-missing metrics.
    for pattern, metric, multiplier in _PATTERNS:
        if metric in extracted:
            continue
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        try:
            parsed = float(raw) * multiplier
            if metric in ("revenue", "cost") and len(match.groups()) > 1:
                parsed *= _unit_multiplier(match.group(2))
            extracted[metric] = parsed
            metric_source[metric] = "parsed_text"
        except ValueError:
            continue

    # Qualitative text overrides (e.g., "high technical debt").
    for metric, rules in _TEXTUAL_OVERRIDES.items():
        if metric in extracted:
            continue
        for pattern, replacement in rules:
            if re.search(pattern, raw_text, flags=re.IGNORECASE):
                extracted[metric] = replacement
                metric_source[metric] = "qualitative_override"
                break

    resolved_profile = _resolve_assumption_profile(raw_text, assumption_profile)

    # Fill missing metrics using profile defaults unless profile="none".
    if resolved_profile != "none":
        defaults = _PROFILE_DEFAULTS.get(resolved_profile, _PROFILE_DEFAULTS["balanced"])
        for metric, default_value in defaults.items():
            if metric in extracted:
                continue
            extracted[metric] = default_value
            metric_source[metric] = f"profile_default:{resolved_profile}"

    # Final sanitation pass.
    sanitized: Dict[str, float] = {}
    for metric, raw_value in extracted.items():
        try:
            sanitized[metric] = _sanitize_metric(metric, float(raw_value))
        except Exception:
            continue

    return sanitized, resolved_profile, metric_source


def generate_advisory_summary(
    snapshot: Dict[str, Any],
    extracted: Dict[str, float],
    assumption_profile: str,
    metric_source: Dict[str, str],
) -> str:
    """Generate a structured advisory narrative from engine output."""
    state = snapshot.get("state", "NORMAL")
    sb = snapshot.get("score_breakdown", {})
    total = sb.get("total_score", 0)
    coeffs = sb.get("coefficient_contributions", [])
    triggered = snapshot.get("triggered_rule_count", 0)
    rule_count = snapshot.get("rule_count", 0)
    restructuring = snapshot.get("restructuring_actions", [])

    lines = []
    lines.append(f"STRATEGOS Diagnostic Summary")
    lines.append(f"{'=' * 40}")
    lines.append(f"")
    lines.append(f"Enterprise State: {state}")
    lines.append(f"Composite Transformation Score: {total:.2f}")
    lines.append(f"Rules Evaluated: {rule_count} | Triggered: {triggered}")
    lines.append(f"Assumption Profile: {assumption_profile}")
    lines.append(f"")

    if coeffs:
        lines.append("Metric Contributions:")
        sorted_coeffs = sorted(coeffs, key=lambda c: abs(c.get("contribution", 0)), reverse=True)
        for c in sorted_coeffs:
            name = c.get("name", "unknown")
            contribution = c.get("contribution", 0)
            mode = c.get("mode", "scalar")
            lines.append(f"  • {name}: {contribution:+.2f} ({mode})")
        lines.append("")

    if state == "CRITICAL_ZONE":
        lines.append("⚠ CRITICAL_ZONE Assessment:")
        lines.append("  The enterprise exhibits transformation urgency requiring immediate executive attention.")
        lines.append("  Multiple risk thresholds have been breached simultaneously.")
        if restructuring:
            lines.append(f"  {len(restructuring)} restructuring directive(s) activated:")
            for r in restructuring:
                payload = r.get("payload", {})
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                lines.append(f"    → {r.get('template_name', 'Action')} (Owner: {payload.get('owner', 'TBD')}, Horizon: {payload.get('horizon', 'TBD')})")
    elif state == "ELEVATED_RISK":
        lines.append("⚡ ELEVATED_RISK Assessment:")
        lines.append("  The enterprise shows elevated transformation pressure.")
        lines.append("  Proactive intervention is recommended before state escalation.")
    else:
        lines.append("✓ NORMAL Assessment:")
        lines.append("  The enterprise operates within acceptable transformation parameters.")
        lines.append("  Continue monitoring key metrics for early-warning signals.")

    lines.append("")
    lines.append("Extracted Input Metrics:")
    for k, v in extracted.items():
        source = metric_source.get(k, "unknown")
        lines.append(f"  {k}: {v} [{source}]")

    return "\n".join(lines)


class IntakeRequest(BaseModel):
    tenant_id: str = ""
    model_version_id: str = ""
    assumption_profile: Optional[str] = Field(
        default=None,
        description="Optional default profile for missing metrics: balanced | growth | stressed | none",
    )
    text: str = Field(..., min_length=5, description="Natural language enterprise description")


@router.post("/intake")
async def natural_language_intake(payload: IntakeRequest, db: AsyncSession = Depends(get_session)):
    """Accept natural language, extract metrics, run engine, return advisory."""

    # 1. Extract structured metrics from natural language
    extracted, resolved_profile, metric_source = extract_metrics(payload.text, payload.assumption_profile)

    # 2. Resolve tenant & model version
    tenant_uuid: Optional[uuid.UUID] = None
    requested_tenant_uuid: Optional[uuid.UUID] = None
    if payload.tenant_id:
        try:
            tenant_uuid = uuid.UUID(payload.tenant_id)
            requested_tenant_uuid = tenant_uuid
        except Exception:
            pass

    model_version_id = payload.model_version_id or None

    # If no model_version_id provided, pick the first active one
    if not model_version_id:
        q = select(models.ModelVersion).where(models.ModelVersion.is_active == True)
        if tenant_uuid:
            q = q.where(models.ModelVersion.tenant_id == tenant_uuid)
        q = q.limit(1)
        res = await db.execute(q)
        mv = res.scalars().first()
        # Fallback for demo/local flows where auth tenant may not match seeded tenant.
        if not mv and tenant_uuid:
            fallback_q = select(models.ModelVersion).where(models.ModelVersion.is_active == True).limit(1)
            fallback_res = await db.execute(fallback_q)
            mv = fallback_res.scalars().first()
        if mv:
            model_version_id = str(mv.id)
            # Keep requested tenant for session visibility in customer-facing UI,
            # even when model-version fallback uses a different seeded tenant.
            tenant_uuid = requested_tenant_uuid or mv.tenant_id
        else:
            raise HTTPException(status_code=404, detail="no_active_model_version")

    if not tenant_uuid:
        # Fallback: get tenant from model version
        try:
            mv_obj = await db.get(models.ModelVersion, uuid.UUID(model_version_id))
            if mv_obj:
                tenant_uuid = requested_tenant_uuid or mv_obj.tenant_id
        except Exception:
            pass

    if not tenant_uuid:
        raise HTTPException(status_code=400, detail="could_not_resolve_tenant")

    # 3. Create session
    session_name = (payload.text[:80] + "…") if len(payload.text) > 80 else payload.text
    stmt = (
        insert(models.TransformationSession)
        .values(
            tenant_id=tenant_uuid,
            model_version_id=uuid.UUID(model_version_id),
            name=session_name,
        )
        .returning(models.TransformationSession.id)
    )
    res = await db.execute(stmt)
    session_id = res.scalar()

    # 4. Run deterministic engine
    snapshot = await run_deterministic_engine(
        db,
        model_version_id=model_version_id,
        input_data=extracted,
    )

    if isinstance(snapshot, dict) and snapshot.get("error"):
        await db.commit()
        raise HTTPException(status_code=400, detail=snapshot)

    # 5. Persist snapshot to session
    packed = json.dumps({
        "version": 1,
        "latest": snapshot,
        "history": [{"version": 1, "created_at": str(uuid.uuid4())[:8], "snapshot": snapshot}],
    })
    await db.execute(
        models.TransformationSession.__table__
        .update()
        .where(models.TransformationSession.id == session_id)
        .values(snapshot=packed)
    )

    # 6. Audit log
    await db.execute(
        insert(models.AuditLog).values(
            tenant_id=tenant_uuid,
            actor="intake_api",
            action="ENGINE_RUN",
            payload=json.dumps({
                "model_version_id": model_version_id,
                "session_id": str(session_id),
                "input": extracted,
                "state": snapshot.get("state"),
                "total_score": (snapshot.get("score_breakdown") or {}).get("total_score"),
                "source": "natural_language_intake",
                "assumption_profile": resolved_profile,
                "metric_source": metric_source,
                "original_text": payload.text[:500],
            }),
        )
    )

    await db.commit()

    # 7. Generate advisory summary
    advisory = generate_advisory_summary(snapshot, extracted, resolved_profile, metric_source)

    return format_response({
        "session_id": str(session_id),
        "extracted_input": extracted,
        "assumption_profile_used": resolved_profile,
        "metric_source": metric_source,
        "snapshot": snapshot,
        "advisory_summary": advisory,
    })
