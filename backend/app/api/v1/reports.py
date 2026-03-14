"""Report generation endpoint.

Generates downloadable PDF executive reports and CSV data exports
from a session's deterministic engine snapshot.
"""

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.session import get_session

router = APIRouter()

_METRIC_LABELS: Dict[str, str] = {
    "margin": "operating margin",
    "technical_debt": "technical debt",
    "cost": "operating costs",
    "revenue": "revenue",
    "revenue_growth_yoy_pct": "revenue growth (YoY)",
    "customer_churn_pct": "customer churn",
    "lead_time_days": "delivery lead time",
    "change_failure_rate_pct": "change failure rate",
    "p1_incidents_per_month": "P1 incidents per month",
    "cyber_findings_open_high": "high-severity cyber findings",
    "regulatory_findings_open": "regulatory findings",
    "critical_role_attrition_pct": "critical-role attrition",
    "vendor_concentration_pct": "vendor concentration",
    "top_customer_concentration_pct": "top-customer concentration",
    "cloud_adoption_pct": "cloud adoption",
    "automation_coverage_pct": "automation coverage",
    "cash_conversion_cycle_days": "cash conversion cycle",
}

_PLAIN_RULE_MAP: Dict[str, str] = {
    "margin < 0.12": "Operating margin is below 12%",
    "technical_debt > 65": "Technical debt is above 65%",
    "cost > (revenue * 0.82)": "Operating costs exceed 82% of revenue",
    "revenue_growth_yoy_pct < 3": "Revenue growth is below 3% YoY",
    "customer_churn_pct > 2.8": "Customer churn is above 2.8%",
    "(lead_time_days > 14) or (change_failure_rate_pct > 20)":
        "Delivery lead time exceeds 14 days or change failure rate is above 20%",
    "p1_incidents_per_month > 5": "P1 incidents exceed 5 per month",
    "(cyber_findings_open_high > 10) or (regulatory_findings_open > 5)":
        "High-severity cyber findings exceed 10 or regulatory findings exceed 5",
    "critical_role_attrition_pct > 12": "Critical-role attrition is above 12%",
    "(vendor_concentration_pct > 50) or (top_customer_concentration_pct > 40)":
        "Vendor concentration exceeds 50% or top-customer concentration exceeds 40%",
    "(cloud_adoption_pct < 40) and (automation_coverage_pct < 40)":
        "Cloud adoption is below 40% and automation coverage is below 40%",
    "cash_conversion_cycle_days > 80": "Cash conversion cycle is above 80 days",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_plain_english_rule(expression: str) -> str:
    raw = (expression or "").strip()
    if not raw:
        return "Rule condition not available"
    direct = _PLAIN_RULE_MAP.get(raw)
    if direct:
        return direct

    out = raw
    for metric, label in _METRIC_LABELS.items():
        out = out.replace(metric, label)
    out = (
        out.replace(">=", " is at least ")
        .replace("<=", " is at most ")
        .replace(">", " is above ")
        .replace("<", " is below ")
        .replace(" and ", " and ")
        .replace(" or ", " or ")
    )
    out = " ".join(out.split())
    if not out:
        return raw
    return out[0].upper() + out[1:]


def _build_csv(session_id: str, snapshot: dict) -> str:
    """Build CSV export from deterministic snapshot."""
    output = io.StringIO()
    writer = csv.writer(output)

    sb = snapshot.get("score_breakdown", {}) or {}
    writer.writerow(["STRATEGOS Executive Data Export"])
    writer.writerow(["Session ID", session_id])
    writer.writerow([])
    writer.writerow(["State Classification", snapshot.get("state", "N/A")])
    writer.writerow(["Total Score", sb.get("total_score", "N/A")])
    writer.writerow(["State Score", sb.get("state_score", "N/A")])
    writer.writerow(["Weighted Input Score", sb.get("weighted_input_score", "N/A")])
    writer.writerow(["Rule Impact Score", sb.get("rule_impact_score", "N/A")])
    writer.writerow(["Rules Evaluated", snapshot.get("rule_count", "N/A")])
    writer.writerow(["Rules Triggered", snapshot.get("triggered_rule_count", "N/A")])
    writer.writerow([])

    coeffs = sb.get("coefficient_contributions", []) or []
    if coeffs:
        writer.writerow(["Coefficient Contributions"])
        writer.writerow(["Driver", "Mode", "Contribution", "Error"])
        for c in sorted(coeffs, key=lambda x: abs(_safe_float(x.get("contribution"))), reverse=True):
            writer.writerow(
                [
                    c.get("name", ""),
                    c.get("mode", ""),
                    c.get("contribution", ""),
                    c.get("error", ""),
                ]
            )
        writer.writerow([])

    contribs = snapshot.get("contributions", []) or []
    if contribs:
        writer.writerow(["Rule Condition Detail"])
        writer.writerow(["Rule Triggered", "Result", "Error"])
        for c in contribs:
            writer.writerow(
                [
                    _to_plain_english_rule(str(c.get("expression") or "")),
                    "TRIGGERED" if bool(c.get("result")) else "OK",
                    c.get("error", ""),
                ]
            )
        writer.writerow([])

    actions = snapshot.get("restructuring_actions", []) or []
    if actions:
        writer.writerow(["Restructuring Actions"])
        writer.writerow(["Template", "Payload"])
        for a in actions:
            payload = a.get("payload", "")
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            writer.writerow([a.get("template_name", ""), payload])
    return output.getvalue()


def _build_pdf(session_id: str, session_name: str, snapshot: dict) -> bytes:
    """Build themed, readable PDF report."""
    try:
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise RuntimeError(f"pdf_dependency_missing:{exc.__class__.__name__}")

    # Theme aligned with STRATEGOS dark UI.
    theme_bg = rl_colors.HexColor("#060a14")
    theme_panel = rl_colors.HexColor("#0a0f1c")
    theme_panel_alt = rl_colors.HexColor("#0f172a")
    theme_border = rl_colors.HexColor("#1e293b")
    theme_text = rl_colors.HexColor("#f8fafc")
    theme_muted = rl_colors.HexColor("#94a3b8")
    theme_accent = rl_colors.HexColor("#f59e0b")
    theme_green = rl_colors.HexColor("#4ade80")
    theme_red = rl_colors.HexColor("#f87171")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="STRATEGOS Executive Transformation Report",
        author="STRATEGOS",
    )

    sb = snapshot.get("score_breakdown", {}) or {}
    state = str(snapshot.get("state") or "UNKNOWN")
    state_color = theme_green
    if state == "ELEVATED_RISK":
        state_color = theme_accent
    elif state == "CRITICAL_ZONE":
        state_color = theme_red

    styles = {
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=theme_text,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=theme_muted,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=theme_accent,
            spaceAfter=4,
            spaceBefore=8,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=theme_text,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=theme_muted,
        ),
    }

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_score = _safe_float(sb.get("total_score"))
    weighted_score = _safe_float(sb.get("weighted_input_score"))
    rule_impact = _safe_float(sb.get("rule_impact_score"))
    state_score = _safe_float(sb.get("state_score"))
    rules_triggered = int(_safe_float(snapshot.get("triggered_rule_count"), 0.0))
    rule_count = int(_safe_float(snapshot.get("rule_count"), 0.0))

    elements = []
    elements.append(Paragraph("STRATEGOS Executive Transformation Report", styles["title"]))
    elements.append(
        Paragraph(
            f"Session: {session_name or session_id}<br/>Session ID: {session_id}<br/>Generated: {generated_at}",
            styles["subtitle"],
        )
    )

    kpis = Table(
        [
            [
                Paragraph(f'<font color="#94a3b8">State</font><br/><font color="{state_color.hexval()}"><b>{state}</b></font>', styles["body"]),
                Paragraph(f'<font color="#94a3b8">Total Score</font><br/><b>{total_score:.2f}</b>', styles["body"]),
                Paragraph(f'<font color="#94a3b8">Rules Triggered</font><br/><b>{rules_triggered}/{rule_count}</b>', styles["body"]),
                Paragraph(f'<font color="#94a3b8">State Score</font><br/><b>{state_score:.2f}</b>', styles["body"]),
            ]
        ],
        colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm],
    )
    kpis.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), theme_panel),
                ("BOX", (0, 0), (-1, -1), 0.8, theme_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, theme_border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(kpis)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Score Breakdown", styles["section"]))
    breakdown = Table(
        [
            ["Weighted Input Score", f"{weighted_score:.2f}"],
            ["Rule Impact Score", f"{rule_impact:.2f}"],
            ["Total Score", f"{total_score:.2f}"],
        ],
        colWidths=[95 * mm, 75 * mm],
    )
    breakdown.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), theme_panel),
                ("TEXTCOLOR", (0, 0), (-1, -1), theme_text),
                ("BOX", (0, 0), (-1, -1), 0.8, theme_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, theme_border),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(breakdown)

    coeffs = sb.get("coefficient_contributions", []) or []
    if coeffs:
        elements.append(Paragraph("Top Coefficient Contributions", styles["section"]))
        coeff_rows: List[List[str]] = [["Driver", "Mode", "Contribution"]]
        sorted_coeffs = sorted(coeffs, key=lambda c: abs(_safe_float(c.get("contribution"))), reverse=True)[:12]
        for c in sorted_coeffs:
            coeff_rows.append(
                [
                    str(c.get("name") or "unknown"),
                    str(c.get("mode") or ""),
                    f"{_safe_float(c.get('contribution')):+.2f}",
                ]
            )
        coeff_table = Table(coeff_rows, colWidths=[90 * mm, 35 * mm, 45 * mm])
        coeff_style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), theme_panel_alt),
                ("TEXTCOLOR", (0, 0), (-1, 0), theme_accent),
                ("BACKGROUND", (0, 1), (-1, -1), theme_panel),
                ("TEXTCOLOR", (0, 1), (-1, -1), theme_text),
                ("BOX", (0, 0), (-1, -1), 0.8, theme_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, theme_border),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
        for idx, row in enumerate(coeff_rows[1:], start=1):
            contribution = _safe_float(row[2])
            coeff_style.add("TEXTCOLOR", (2, idx), (2, idx), theme_red if contribution > 0 else theme_green)
        coeff_table.setStyle(coeff_style)
        elements.append(coeff_table)

    contribs = snapshot.get("contributions", []) or []
    if contribs:
        elements.append(Paragraph("Rule Condition Detail", styles["section"]))
        rule_rows: List[List[object]] = [["Rule Triggered", "Result"]]
        for c in contribs:
            expression = str(c.get("expression") or "")
            rule_rows.append(
                [
                    Paragraph(_to_plain_english_rule(expression), styles["body"]),
                    "TRIGGERED" if bool(c.get("result")) else "OK",
                ]
            )
        rule_table = Table(rule_rows, colWidths=[145 * mm, 25 * mm])
        rule_style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), theme_panel_alt),
                ("TEXTCOLOR", (0, 0), (-1, 0), theme_accent),
                ("BACKGROUND", (0, 1), (-1, -1), theme_panel),
                ("TEXTCOLOR", (0, 1), (0, -1), theme_text),
                ("BOX", (0, 0), (-1, -1), 0.8, theme_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, theme_border),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ]
        )
        for idx, c in enumerate(contribs, start=1):
            rule_style.add("TEXTCOLOR", (1, idx), (1, idx), theme_red if bool(c.get("result")) else theme_green)
        rule_table.setStyle(rule_style)
        elements.append(rule_table)

    actions = snapshot.get("restructuring_actions", []) or []
    if actions:
        elements.append(Paragraph("Restructuring Roadmap", styles["section"]))
        action_rows: List[List[str]] = [["Action", "Owner", "Horizon"]]
        for action in actions[:12]:
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            owner = str((payload or {}).get("owner") or "Executive Team")
            horizon_days = (payload or {}).get("horizon_days")
            horizon = f"{horizon_days} days" if horizon_days is not None else "90 days"
            action_rows.append([str(action.get("template_name") or "action"), owner, horizon])
        action_table = Table(action_rows, colWidths=[90 * mm, 45 * mm, 35 * mm])
        action_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), theme_panel_alt),
                    ("TEXTCOLOR", (0, 0), (-1, 0), theme_accent),
                    ("BACKGROUND", (0, 1), (-1, -1), theme_panel),
                    ("TEXTCOLOR", (0, 1), (-1, -1), theme_text),
                    ("BOX", (0, 0), (-1, -1), 0.8, theme_border),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, theme_border),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(action_table)

    elements.append(Spacer(1, 8))
    elements.append(
        Paragraph(
            "Generated by STRATEGOS Deterministic Transformation Engine. "
            "This report preserves platform visual identity while optimizing readability for print/export.",
            styles["small"],
        )
    )

    def _draw_page_background(canvas, _doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(theme_bg)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.restoreState()

    doc.build(elements, onFirstPage=_draw_page_background, onLaterPages=_draw_page_background)
    buffer.seek(0)
    return buffer.read()


@router.get("/reports/{session_id}")
async def generate_report(
    session_id: str,
    format: str = Query("pdf", description="Report format: pdf or csv"),
    db: AsyncSession = Depends(get_session),
):
    """Generate downloadable report for a session."""
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
    fmt = (format or "pdf").strip().lower()

    if fmt == "csv":
        csv_data = _build_csv(str(sid), snapshot)
        return StreamingResponse(
            io.BytesIO(csv_data.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="strategos_{session_id}.csv"'},
        )

    if fmt == "pdf":
        try:
            pdf_data = _build_pdf(str(sid), session_name, snapshot)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return StreamingResponse(
            io.BytesIO(pdf_data),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="strategos_{session_id}_report.pdf"'},
        )

    raise HTTPException(status_code=400, detail="unsupported_report_format")
