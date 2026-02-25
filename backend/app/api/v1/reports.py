"""Report generation endpoint.

Generates downloadable PDF executive reports and CSV data exports
from a session's engine snapshot.
"""

import csv
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.session import get_session

router = APIRouter()


def _build_csv(session_id: str, snapshot: dict) -> str:
    """Build a CSV export from engine snapshot."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["STRATEGOS Executive Data Export"])
    writer.writerow(["Session ID", session_id])
    writer.writerow([])

    # State & Score
    sb = snapshot.get("score_breakdown", {})
    writer.writerow(["State Classification", snapshot.get("state", "N/A")])
    writer.writerow(["Total Score", sb.get("total_score", "N/A")])
    writer.writerow(["Weighted Input Score", sb.get("weighted_input_score", "N/A")])
    writer.writerow(["Rule Impact Score", sb.get("rule_impact_score", "N/A")])
    writer.writerow(["Rules Evaluated", snapshot.get("rule_count", "N/A")])
    writer.writerow(["Rules Triggered", snapshot.get("triggered_rule_count", "N/A")])
    writer.writerow([])

    # Scores map
    scores = snapshot.get("scores", {})
    if scores:
        writer.writerow(["Metric Scores"])
        writer.writerow(["Metric", "Value"])
        for k, v in scores.items():
            writer.writerow([k, v])
        writer.writerow([])

    # Coefficient Contributions
    coeffs = sb.get("coefficient_contributions", [])
    if coeffs:
        writer.writerow(["Coefficient Contributions"])
        writer.writerow(["Name", "Value", "Weight", "Mode", "Contribution"])
        for c in coeffs:
            writer.writerow([
                c.get("name", ""),
                c.get("value", ""),
                c.get("weight", ""),
                c.get("mode", ""),
                c.get("contribution", ""),
            ])
        writer.writerow([])

    # Contributions (rule impacts)
    contribs = snapshot.get("contributions", [])
    if contribs:
        writer.writerow(["Rule Contributions"])
        writer.writerow(["Rule", "Impact Field", "Impact Value", "Conditions Evaluated"])
        for c in contribs:
            writer.writerow([
                c.get("rule_name", ""),
                c.get("impact_field", ""),
                c.get("impact_value", ""),
                c.get("conditions_evaluated", ""),
            ])
        writer.writerow([])

    # Restructuring Actions
    actions = snapshot.get("restructuring_actions", [])
    if actions:
        writer.writerow(["Restructuring Actions"])
        writer.writerow(["Template", "Payload"])
        for a in actions:
            payload = a.get("payload", "")
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            writer.writerow([a.get("template_name", ""), payload])

    return output.getvalue()


def _build_pdf_text(session_id: str, session_name: str, snapshot: dict) -> str:
    """Build a plain-text PDF-like report.
    
    Note: For true PDF rendering, install fpdf2 and replace this with
    actual PDF generation. This returns a well-formatted text report
    that works universally without additional dependencies.
    """
    sb = snapshot.get("score_breakdown", {})
    state = snapshot.get("state", "UNKNOWN")
    total = sb.get("total_score", 0)
    w_input = sb.get("weighted_input_score", 0)
    rule_impact = sb.get("rule_impact_score", 0)
    coeffs = sb.get("coefficient_contributions", [])
    contribs = snapshot.get("contributions", [])
    actions = snapshot.get("restructuring_actions", [])
    scores = snapshot.get("scores", {})

    lines = []
    lines.append("╔══════════════════════════════════════════════════════════════╗")
    lines.append("║         STRATEGOS  ·  EXECUTIVE TRANSFORMATION REPORT       ║")
    lines.append("╚══════════════════════════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"Session:  {session_name or session_id}")
    lines.append(f"ID:       {session_id}")
    lines.append(f"")
    lines.append("─" * 62)
    lines.append("  ENTERPRISE STATE CLASSIFICATION")
    lines.append("─" * 62)
    lines.append(f"  State:                {state}")
    lines.append(f"  Composite Score:      {total:.4f}")
    lines.append(f"  Weighted Input Score: {w_input:.4f}")
    lines.append(f"  Rule Impact Score:    {rule_impact:.4f}")
    lines.append(f"  Rules Evaluated:      {snapshot.get('rule_count', 0)}")
    lines.append(f"  Rules Triggered:      {snapshot.get('triggered_rule_count', 0)}")
    lines.append(f"  Conditions Evaluated: {snapshot.get('conditions_evaluated', 0)}")
    lines.append("")

    if scores:
        lines.append("─" * 62)
        lines.append("  METRIC SCORES")
        lines.append("─" * 62)
        for k, v in scores.items():
            lines.append(f"  {k:<30} {v}")
        lines.append("")

    if coeffs:
        lines.append("─" * 62)
        lines.append("  COEFFICIENT CONTRIBUTIONS")
        lines.append("─" * 62)
        sorted_c = sorted(coeffs, key=lambda c: abs(c.get("contribution", 0)), reverse=True)
        for c in sorted_c:
            name = c.get("name", "unknown")
            contribution = c.get("contribution", 0)
            weight = c.get("weight", 0)
            mode = c.get("mode", "scalar")
            lines.append(f"  {name:<20} contribution={contribution:+.4f}  weight={weight}  mode={mode}")
        lines.append("")

    if contribs:
        lines.append("─" * 62)
        lines.append("  RULE CONTRIBUTIONS")
        lines.append("─" * 62)
        for c in contribs:
            lines.append(f"  Rule: {c.get('rule_name', 'N/A')}")
            lines.append(f"    Impact: {c.get('impact_field', '')} = {c.get('impact_value', '')}")
            lines.append(f"    Conditions: {c.get('conditions_evaluated', 0)} evaluated")
        lines.append("")

    if actions:
        lines.append("─" * 62)
        lines.append("  RESTRUCTURING DIRECTIVES")
        lines.append("─" * 62)
        for a in actions:
            payload = a.get("payload", {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            lines.append(f"  Template: {a.get('template_name', 'N/A')}")
            if isinstance(payload, dict):
                for pk, pv in payload.items():
                    lines.append(f"    {pk}: {pv}")
            lines.append("")

    # Assessment
    lines.append("─" * 62)
    lines.append("  ADVISORY ASSESSMENT")
    lines.append("─" * 62)
    if state == "CRITICAL_ZONE":
        lines.append("  The enterprise is in CRITICAL_ZONE requiring immediate")
        lines.append("  executive attention. Transformation urgency is at maximum.")
        lines.append(f"  {len(actions)} restructuring directive(s) have been activated.")
    elif state == "ELEVATED_RISK":
        lines.append("  The enterprise exhibits ELEVATED_RISK indicators.")
        lines.append("  Proactive intervention recommended to prevent escalation.")
    else:
        lines.append("  The enterprise operates within NORMAL parameters.")
        lines.append("  Continue monitoring for early-warning signals.")
    lines.append("")
    lines.append("─" * 62)
    lines.append("  Generated by STRATEGOS Deterministic Transformation Engine")
    lines.append("  © 2025 STRATEGOS Platform · Confidential")
    lines.append("─" * 62)

    return "\n".join(lines)


@router.get("/reports/{session_id}")
async def generate_report(
    session_id: str,
    format: str = Query("pdf", description="Report format: pdf or csv"),
    db: AsyncSession = Depends(get_session),
):
    """Generate a downloadable report for a session."""
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    if not session_obj.snapshot:
        raise HTTPException(status_code=400, detail="session_has_no_snapshot")

    try:
        snapshot_wrapper = json.loads(session_obj.snapshot)
    except Exception:
        raise HTTPException(status_code=500, detail="invalid_snapshot_format")

    snapshot = snapshot_wrapper.get("latest") or snapshot_wrapper
    session_name = session_obj.name or ""

    if format == "csv":
        csv_data = _build_csv(str(sid), snapshot)
        return StreamingResponse(
            io.BytesIO(csv_data.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="strategos_{session_id}.csv"'},
        )
    else:
        # Text-based report (styled as PDF-like output)
        # For true PDF, replace with fpdf2 or weasyprint generation
        report_text = _build_pdf_text(str(sid), session_name, snapshot)
        return StreamingResponse(
            io.BytesIO(report_text.encode("utf-8")),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="strategos_{session_id}_report.txt"'},
        )
