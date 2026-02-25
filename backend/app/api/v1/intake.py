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
    # revenue  – "$640M", "640 million revenue", "revenue of 640", "640M revenue"
    # number followed shortly by revenue keyword (keeps proximity to avoid earlier numbers capturing)
    (r"(?:\$\s*)?([\d,.]+)\s*(?:m(?:illion)?|b(?:illion)?|bn|b)\b(?:[^\.\n]{0,40})?(?:revenue|turnover|sales)", "revenue", 1.0),
    (r"(?:revenue|turnover|sales)\s*(?:of|at|around|≈|~)?\s*\$?\s*([\d,.]+)\s*(?:m(?:illion)?|b(?:illion)?|bn|b)?", "revenue", 1.0),

    # cost / opex – "$335M cost", "operating costs 335M", "OPEX of 335"
    (r"(?:\$\s*)?([\d,.]+)\s*(?:m(?:illion)?|b(?:illion)?|bn|b)\b(?:[^\.\n]{0,40})?(?:cost|opex|expenditure|capex)", "cost", 1.0),
    (r"(?:cost|opex|expenditure|capex|operating\s+cost)\s*(?:of|at|around|≈|~)?\s*\$?\s*([\d,.]+)\s*(?:m(?:illion)?|b(?:illion)?|bn|b)?", "cost", 1.0),

    # margin – "8% margin", "margins at 0.08", "margin of 8%"
    (r"([\d,.]+)\s*%\s*(?:margin|ebitda|operating\s+margin)", "margin", 0.01),
    (r"(?:margin|ebitda)\s*(?:of|at|around|≈|~)?\s*([\d,.]+)\s*%", "margin", 0.01),
    (r"(?:margin|ebitda)\s*(?:of|at|around|≈|~)?\s*(0\.\d+)", "margin", 1.0),

    # technical_debt – "92% technical debt", "tech debt around 92", "high legacy debt of 85"
    (r"(?:technical?\s*debt|tech\s*debt|legacy\s*debt)\s*(?:of|at|around|≈|~|score)?\s*([\d,.]+)\s*%?", "technical_debt", 1.0),
    (r"([\d,.]+)\s*%?\s*(?:technical?\s*debt|tech\s*debt|legacy\s*debt)", "technical_debt", 1.0),
]

# Heuristic defaults when only partial data is extracted
_DEFAULTS: Dict[str, float] = {
    "revenue": 800.0,
    "cost": 250.0,
    "margin": 0.15,
    "technical_debt": 60.0,
}

# Keyword-sentiment heuristics to nudge missing metrics
_SEVERITY_KEYWORDS = {
    "critical": 1.4,
    "severe": 1.3,
    "high": 1.2,
    "legacy": 1.15,
    "declining": 1.15,
    "pressure": 1.1,
    "low": 0.85,
    "stable": 0.95,
    "healthy": 0.8,
    "strong": 0.75,
    "modern": 0.7,
}

_EXPLICIT_LABEL_PATTERNS: List[Tuple[str, str]] = [
    (r"\brevenue\s*[:=]\s*\$?\s*([\d,.]+)\s*(m|million|bn|billion|b)?\b", "revenue"),
    (r"\b(?:operating\s+)?costs?\s*[:=]\s*\$?\s*([\d,.]+)\s*(m|million|bn|billion|b)?\b", "cost"),
    (r"\b(?:margin|operating\s+margin)\s*[:=]\s*([\d,.]+)\s*%?\b", "margin"),
    (r"\b(?:technical\s+debt|tech\s+debt)\s*[:=]\s*([\d,.]+)\s*%?\b", "technical_debt"),
]


def _unit_multiplier(unit: Optional[str]) -> float:
    if not unit:
        return 1.0
    u = unit.lower()
    if u in ("bn", "billion", "b"):
        return 1000.0
    return 1.0


def extract_metrics(text: str) -> Dict[str, float]:
    """Deterministic regex-based metric extraction from natural language."""
    # Use case-insensitive regex matching against original text to avoid
    # issues with upper/lower-case unit tokens (e.g. 'M', 'BN') and preserve
    # surrounding words for pattern context.
    extracted: Dict[str, float] = {}

    # 0) Prefer explicit "Metric: value" inputs produced by the frontend confirmation payload.
    for pattern, metric in _EXPLICIT_LABEL_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
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

    for pattern, metric, multiplier in _PATTERNS:
        if metric in extracted:
            continue
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                extracted[metric] = float(raw) * multiplier
            except ValueError:
                continue

    # Apply severity heuristics for missing metrics
    severity = 1.0
    # lower-case copy for keyword checks
    text_lower = (text or "").lower()
    for kw, factor in _SEVERITY_KEYWORDS.items():
        if kw in text_lower:
            severity = max(severity, factor)

    for metric, default in _DEFAULTS.items():
        if metric not in extracted:
            if metric in ("cost", "technical_debt"):
                extracted[metric] = round(default * severity, 2)
            elif metric in ("margin",):
                extracted[metric] = round(default / severity, 4)
            else:
                extracted[metric] = round(default / severity, 2)

    return extracted


def generate_advisory_summary(snapshot: Dict[str, Any], extracted: Dict[str, float]) -> str:
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
        lines.append(f"  {k}: {v}")

    return "\n".join(lines)


class IntakeRequest(BaseModel):
    tenant_id: str = ""
    model_version_id: str = ""
    text: str = Field(..., min_length=5, description="Natural language enterprise description")


@router.post("/intake")
async def natural_language_intake(payload: IntakeRequest, db: AsyncSession = Depends(get_session)):
    """Accept natural language, extract metrics, run engine, return advisory."""

    # 1. Extract structured metrics from natural language
    extracted = extract_metrics(payload.text)

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
                "original_text": payload.text[:500],
            }),
        )
    )

    await db.commit()

    # 7. Generate advisory summary
    advisory = generate_advisory_summary(snapshot, extracted)

    return format_response({
        "session_id": str(session_id),
        "extracted_input": extracted,
        "snapshot": snapshot,
        "advisory_summary": advisory,
    })
