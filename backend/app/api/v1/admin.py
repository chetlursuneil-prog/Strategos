"""Admin Command endpoint.

Accepts natural language admin instructions and routes them to the
appropriate backend operations (create model versions, manage rules,
view audit logs, etc.)  Zero JSON knowledge required from the user.
"""

import re
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import format_response
from app.db import models
from app.db.session import get_session

router = APIRouter()

BOARD_PATH = Path(__file__).resolve().parents[3] / "openclaw" / "agents" / "strategos_advisory_board.json"
SKILLS_PATH = Path(__file__).resolve().parents[3] / "openclaw" / "skills" / "strategos_skills.json"


# ── Intent patterns ──────────────────────────────────────────────────────

def _match(text: str, patterns: List[str]) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def _extract_quoted(text: str) -> Optional[str]:
    """Extract first quoted string or string after 'called/named'."""
    m = re.search(r'["\u201c](.+?)["\u201d]', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:called|named|titled)\s+(.+?)(?:\s+(?:with|that|for|$))', text, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".")
    return None


def _extract_description(text: str) -> Optional[str]:
    """Extract description after 'with description' or 'described as'."""
    m = re.search(r'(?:with\s+description|described\s+as|description[:\s]+)["\u201c]?(.+?)["\u201d]?$', text, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".")
    return None


# ── Route handlers ───────────────────────────────────────────────────────

class AdminCommand(BaseModel):
    tenant_id: str = ""
    text: str = Field(..., min_length=3, description="Natural language admin command")


class AdminAgentCreate(BaseModel):
    id: str = Field(..., min_length=2)
    role: str = Field(..., min_length=3)
    skills: List[str] = Field(default_factory=list)


class AdminAgentSkillsUpdate(BaseModel):
    skills: List[str] = Field(default_factory=list)


def _load_json_config(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return default


def _write_json_config(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_board_payload() -> Dict[str, Any]:
    return _load_json_config(BOARD_PATH, {"agents": []})


def _extract_skill_catalog() -> List[str]:
    payload = _load_json_config(SKILLS_PATH, {"skills": []})
    items = payload.get("skills")
    if not isinstance(items, list):
        return []
    skill_ids: List[str] = []
    for item in items:
        if isinstance(item, dict):
            sid = item.get("id")
            if isinstance(sid, str) and sid.strip():
                skill_ids.append(sid.strip())
    return skill_ids


def _normalize_skills(skills: List[str]) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for raw in skills:
        if not isinstance(raw, str):
            continue
        val = raw.strip()
        if not val or val in seen:
            continue
        deduped.append(val)
        seen.add(val)
    return deduped


@router.get("/admin/agents")
async def list_admin_agents():
    board = _load_board_payload()
    agents_raw = board.get("agents")
    agents = [a for a in agents_raw if isinstance(a, dict)] if isinstance(agents_raw, list) else []
    available_skills = _extract_skill_catalog()

    return format_response({
        "action": "list_agents",
        "message": f"Found {len(agents)} configured agent(s).",
        "agents": agents,
        "available_skills": available_skills,
    })


@router.post("/admin/agents")
async def create_admin_agent(payload: AdminAgentCreate):
    board = _load_board_payload()
    agents_raw = board.get("agents")
    agents = [a for a in agents_raw if isinstance(a, dict)] if isinstance(agents_raw, list) else []
    agent_id = payload.id.strip()

    if any(str(a.get("id") or "").strip() == agent_id for a in agents):
        raise HTTPException(status_code=409, detail="agent_id_already_exists")

    next_agent = {
        "id": agent_id,
        "role": payload.role.strip(),
        "skills": _normalize_skills(payload.skills),
    }
    agents.append(next_agent)
    board["agents"] = agents
    _write_json_config(BOARD_PATH, board)

    return format_response({
        "action": "agent_created",
        "message": f"Agent '{agent_id}' created.",
        "agent": next_agent,
    })


@router.put("/admin/agents/{agent_id}/skills")
async def update_admin_agent_skills(agent_id: str, payload: AdminAgentSkillsUpdate):
    board = _load_board_payload()
    agents_raw = board.get("agents")
    agents = [a for a in agents_raw if isinstance(a, dict)] if isinstance(agents_raw, list) else []

    target = None
    for a in agents:
        if str(a.get("id") or "").strip() == agent_id.strip():
            target = a
            break
    if target is None:
        raise HTTPException(status_code=404, detail="agent_not_found")

    normalized_skills = _normalize_skills(payload.skills)
    target["skills"] = normalized_skills
    board["agents"] = agents
    _write_json_config(BOARD_PATH, board)

    available_skills = set(_extract_skill_catalog())
    unknown_skills = [s for s in normalized_skills if s not in available_skills]

    return format_response({
        "action": "agent_skills_updated",
        "message": f"Skills updated for agent '{agent_id}'.",
        "agent": target,
        "unknown_skills": unknown_skills,
    })


@router.delete("/admin/agents/{agent_id}")
async def remove_admin_agent(agent_id: str):
    board = _load_board_payload()
    agents_raw = board.get("agents")
    agents = [a for a in agents_raw if isinstance(a, dict)] if isinstance(agents_raw, list) else []

    before = len(agents)
    filtered = [a for a in agents if str(a.get("id") or "").strip() != agent_id.strip()]
    if len(filtered) == before:
        raise HTTPException(status_code=404, detail="agent_not_found")

    board["agents"] = filtered
    _write_json_config(BOARD_PATH, board)

    return format_response({
        "action": "agent_removed",
        "message": f"Agent '{agent_id}' removed.",
        "agent_id": agent_id,
    })


@router.post("/admin/command")
async def admin_command(payload: AdminCommand, db: AsyncSession = Depends(get_session)):
    """Interpret a natural language admin command and execute it."""
    text = payload.text.strip()
    text_lower = text.lower()

    # Resolve tenant
    tenant_uuid: Optional[uuid.UUID] = None
    if payload.tenant_id:
        try:
            tenant_uuid = uuid.UUID(payload.tenant_id)
        except Exception:
            pass

    if not tenant_uuid:
        # Try to find any tenant
        res = await db.execute(select(models.Tenant).limit(1))
        t = res.scalars().first()
        if t:
            tenant_uuid = t.id
        else:
            raise HTTPException(status_code=400, detail="no_tenant_found")

    # ────────────── PLATFORM OVERVIEW ──────────────
    if _match(text, [r'overview|status|stats|statistics|platform\s+(?:info|health|summary)|dashboard|show\s+me\s+(?:everything|the\s+platform)']):
        return await _platform_overview(db, tenant_uuid)

    # ────────────── MODEL VERSION CREATION ──────────────
    if _match(text, [r'create\s+(?:a\s+)?(?:new\s+)?model', r'add\s+(?:a\s+)?(?:new\s+)?model', r'new\s+model\s+version']):
        name = _extract_quoted(text)
        if not name:
            # Try to grab everything after "called/named" or after "model version"
            m = re.search(r'model\s*(?:version)?\s+(.+)', text_lower)
            if m:
                name = m.group(1).strip().rstrip(".")
                # Remove filler words
                name = re.sub(r'^(?:called|named|titled)\s+', '', name, flags=re.IGNORECASE)
            if not name:
                name = "New Model Version"
        description = _extract_description(text)

        stmt = (
            insert(models.ModelVersion)
            .values(
                tenant_id=tenant_uuid,
                name=name,
                description=description or f"Created via admin command: {text[:100]}",
                is_active=False,
            )
            .returning(models.ModelVersion.id)
        )
        res = await db.execute(stmt)
        mv_id = res.scalar()
        await db.commit()

        return format_response({
            "action": "model_version_created",
            "message": f'Model version "{name}" has been created successfully. Use "activate model {name}" to make it the active version.',
            "model_version_id": str(mv_id),
            "name": name,
        })

    # ────────────── ACTIVATE MODEL VERSION ──────────────
    if _match(text, [r'activate\s+model', r'switch\s+(?:to\s+)?model', r'enable\s+model', r'set\s+(?:active\s+)?model']):
        target_name = _extract_quoted(text)
        if not target_name:
            m = re.search(r'(?:activate|switch\s+to|enable|set\s+active)\s+(?:model\s*(?:version)?\s*)?(.+)', text_lower)
            if m:
                target_name = m.group(1).strip().rstrip(".")
        if not target_name:
            return format_response({"action": "error", "message": "Please specify which model version to activate. Example: 'Activate model version Q1 Strategy'"})

        # Find by name (fuzzy)
        q = select(models.ModelVersion).where(models.ModelVersion.tenant_id == tenant_uuid)
        res = await db.execute(q)
        versions = res.scalars().all()
        match = None
        for v in versions:
            if target_name.lower() in (v.name or "").lower():
                match = v
                break
        if not match:
            names = [v.name for v in versions]
            return format_response({"action": "error", "message": f'Could not find model version matching "{target_name}". Available: {", ".join(names) or "none"}'})

        # Deactivate all, activate match
        await db.execute(update(models.ModelVersion).where(models.ModelVersion.tenant_id == tenant_uuid).values(is_active=False))
        await db.execute(update(models.ModelVersion).where(models.ModelVersion.id == match.id).values(is_active=True))
        await db.commit()

        return format_response({
            "action": "model_version_activated",
            "message": f'Model version "{match.name}" is now the active version.',
            "model_version_id": str(match.id),
        })

    # ────────────── LIST MODEL VERSIONS ──────────────
    if _match(text, [r'(?:list|show|get|view)\s+(?:all\s+)?model', r'what\s+model', r'which\s+model']):
        q = select(models.ModelVersion).where(models.ModelVersion.tenant_id == tenant_uuid)
        res = await db.execute(q)
        versions = res.scalars().all()

        # Fallback: when sessions exist but model versions belong to another seeded tenant,
        # surface those linked model versions so admin users can still inspect the effective config.
        if not versions:
            sess_q = (
                select(models.TransformationSession.model_version_id)
                .where(models.TransformationSession.tenant_id == tenant_uuid)
                .order_by(models.TransformationSession.created_at.desc())
                .limit(20)
            )
            sess_res = await db.execute(sess_q)
            mv_ids = [row[0] for row in sess_res.all() if row and row[0]]
            if mv_ids:
                fallback_q = select(models.ModelVersion).where(models.ModelVersion.id.in_(mv_ids))
                fallback_res = await db.execute(fallback_q)
                versions = fallback_res.scalars().all()

        items = [{
            "id": str(v.id),
            "name": v.name,
            "description": v.description,
            "is_active": bool(v.is_active),
            "created_at": v.created_at.isoformat() if v.created_at else None,
        } for v in versions]
        return format_response({
            "action": "list_model_versions",
            "message": f"Found {len(items)} model version(s).",
            "model_versions": items,
        })

    # ────────────── CREATE RULE ──────────────
    if _match(text, [r'create\s+(?:a\s+)?(?:new\s+)?rule', r'add\s+(?:a\s+)?(?:new\s+)?rule', r'new\s+rule']):
        name = _extract_quoted(text)
        description = _extract_description(text)

        if not name:
            # Attempt to extract from "rule called X" or "rule: X"
            m = re.search(r'rule\s*(?:called|named|titled|:)?\s+(.+?)(?:\s+(?:that|which|with|for|when))', text, re.IGNORECASE)
            if m:
                name = m.group(1).strip().strip('"').rstrip(".")
            else:
                m = re.search(r'rule\s*(?:called|named|titled|:)?\s+(.+)', text, re.IGNORECASE)
                if m:
                    name = m.group(1).strip().strip('"').rstrip(".")
            if not name:
                name = "New Rule"

        # Find active model version
        q = select(models.ModelVersion).where(
            models.ModelVersion.tenant_id == tenant_uuid,
            models.ModelVersion.is_active == True
        ).limit(1)
        res = await db.execute(q)
        mv = res.scalars().first()
        if not mv:
            return format_response({"action": "error", "message": "No active model version found. Create and activate one first."})

        stmt = (
            insert(models.Rule)
            .values(
                tenant_id=tenant_uuid,
                model_version_id=mv.id,
                name=name,
                description=description or text[:200],
                is_active=True,
            )
            .returning(models.Rule.id)
        )
        res = await db.execute(stmt)
        rule_id = res.scalar()

        # Try to extract condition from "when X" or "if X" or "where X"
        cond_match = re.search(r'(?:when|if|where|condition[:\s]+)\s+(.+?)(?:\s+then|\s+set|\s+apply|$)', text, re.IGNORECASE)
        condition_text = None
        if cond_match:
            condition_text = cond_match.group(1).strip().rstrip(".")
            # Convert NL condition to expression
            expression = _nl_to_condition(condition_text)
            await db.execute(
                insert(models.RuleCondition).values(
                    tenant_id=tenant_uuid,
                    rule_id=rule_id,
                    expression=expression,
                    is_active=True,
                )
            )

        # Try to extract impact from "then X" or "set X" or "apply X"
        impact_match = re.search(r'(?:then|set|apply|impact[:\s]+)\s+(.+?)$', text, re.IGNORECASE)
        impact_text = None
        if impact_match:
            impact_text = impact_match.group(1).strip().rstrip(".")
            impact_expr = _nl_to_impact(impact_text)
            await db.execute(
                insert(models.RuleImpact).values(
                    tenant_id=tenant_uuid,
                    rule_id=rule_id,
                    impact=impact_expr,
                    is_active=True,
                )
            )

        await db.commit()

        result_msg = f'Rule "{name}" created successfully'
        if condition_text:
            result_msg += f' with condition: {condition_text}'
        if impact_text:
            result_msg += f' and impact: {impact_text}'

        return format_response({
            "action": "rule_created",
            "message": result_msg + ".",
            "rule_id": str(rule_id),
            "name": name,
            "condition": condition_text,
            "impact": impact_text,
        })

    # ────────────── DEACTIVATE / DELETE RULE ──────────────
    if _match(text, [r'(?:deactivate|disable|remove|delete)\s+rule']):
        target_name = _extract_quoted(text)
        if not target_name:
            m = re.search(r'(?:deactivate|disable|remove|delete)\s+rule\s+(.+)', text, re.IGNORECASE)
            if m:
                target_name = m.group(1).strip().rstrip(".")

        if not target_name:
            return format_response({"action": "error", "message": 'Please specify which rule to deactivate. Example: \'Deactivate rule "High Debt Alert"\''})

        q = select(models.Rule).where(models.Rule.tenant_id == tenant_uuid, models.Rule.is_active == True)
        res = await db.execute(q)
        rules = res.scalars().all()
        match = None
        for r in rules:
            if target_name.lower() in (r.name or "").lower():
                match = r
                break
        if not match:
            names = [r.name for r in rules]
            return format_response({"action": "error", "message": f'Could not find active rule matching "{target_name}". Active rules: {", ".join(names) or "none"}'})

        await db.execute(update(models.Rule).where(models.Rule.id == match.id).values(is_active=False))
        await db.commit()
        return format_response({
            "action": "rule_deactivated",
            "message": f'Rule "{match.name}" has been deactivated.',
            "rule_id": str(match.id),
        })

    # ────────────── LIST RULES ──────────────
    if _match(text, [r'(?:list|show|get|view)\s+(?:all\s+)?rule', r'what\s+rules?', r'which\s+rules?']):
        q = (
            select(models.Rule)
            .where(models.Rule.tenant_id == tenant_uuid)
            .order_by(models.Rule.created_at.desc())
        )
        res = await db.execute(q)
        rules = res.scalars().all()
        items = []
        for r in rules:
            # Get conditions
            cq = select(models.RuleCondition).where(models.RuleCondition.rule_id == r.id)
            cres = await db.execute(cq)
            conditions = [{"id": str(c.id), "expression": c.expression, "is_active": bool(c.is_active)} for c in cres.scalars().all()]

            # Get impacts
            iq = select(models.RuleImpact).where(models.RuleImpact.rule_id == r.id)
            ires = await db.execute(iq)
            impacts = [{"id": str(im.id), "impact": im.impact, "is_active": bool(im.is_active)} for im in ires.scalars().all()]

            items.append({
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "is_active": bool(r.is_active),
                "conditions": conditions,
                "impacts": impacts,
            })

        return format_response({
            "action": "list_rules",
            "message": f"Found {len(items)} rule(s).",
            "rules": items,
        })

    # ────────────── LIST / SHOW STATES ──────────────
    if _match(text, [r'(?:list|show|get|view)\s+(?:all\s+)?state', r'what\s+states?', r'which\s+states?', r'state\s+definitions?']):
        q = select(models.StateDefinition).where(models.StateDefinition.tenant_id == tenant_uuid)
        res = await db.execute(q)
        states = res.scalars().all()
        items = []
        for s in states:
            tq = select(models.StateThreshold).where(models.StateThreshold.state_definition_id == s.id)
            tres = await db.execute(tq)
            thresholds = [{"id": str(t.id), "threshold": t.threshold} for t in tres.scalars().all()]
            items.append({
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "thresholds": thresholds,
            })

        return format_response({
            "action": "list_states",
            "message": f"Found {len(items)} state definition(s).",
            "states": items,
        })

    # ────────────── AUDIT LOGS ──────────────
    if _match(text, [r'audit', r'(?:activity|event)\s+(?:log|history|trail)', r'what\s+happened', r'recent\s+(?:activity|actions|events)', r'show\s+(?:me\s+)?(?:the\s+)?logs?']):
        q = (
            select(models.AuditLog)
            .where(models.AuditLog.tenant_id == tenant_uuid)
            .order_by(models.AuditLog.created_at.desc())
            .limit(30)
        )
        res = await db.execute(q)
        logs = res.scalars().all()
        items = []
        for log in logs:
            parsed = None
            if log.payload:
                try:
                    parsed = json.loads(log.payload)
                except Exception:
                    parsed = {"raw": log.payload}
            items.append({
                "id": str(log.id),
                "actor": log.actor,
                "action": log.action,
                "payload": parsed,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return format_response({
            "action": "list_audit_logs",
            "message": f"Showing {len(items)} recent audit events.",
            "audit_logs": items,
        })

    # ────────────── SESSIONS LIST ──────────────
    if _match(text, [r'(?:list|show|get|view)\s+(?:all\s+)?session', r'what\s+sessions?', r'recent\s+sessions?']):
        q = (
            select(models.TransformationSession)
            .where(models.TransformationSession.tenant_id == tenant_uuid)
            .order_by(models.TransformationSession.created_at.desc())
            .limit(20)
        )
        res = await db.execute(q)
        sessions = res.scalars().all()
        items = [{
            "id": str(s.id),
            "name": s.name,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "has_snapshot": bool(s.snapshot),
        } for s in sessions]

        return format_response({
            "action": "list_sessions",
            "message": f"Found {len(items)} session(s).",
            "sessions": items,
        })

    # ────────────── DELETE SESSION ──────────────
    if _match(text, [r'(?:delete|remove)\s+session']):
        sid_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', text_lower)
        if not sid_match:
            return format_response({
                "action": "error",
                "message": 'Please specify a session UUID. Example: delete session 123e4567-e89b-12d3-a456-426614174000',
            })
        try:
            sid = uuid.UUID(sid_match.group(1))
        except Exception:
            return format_response({"action": "error", "message": "Invalid session UUID format."})

        session_obj = await db.get(models.TransformationSession, sid)
        if session_obj is None:
            return format_response({"action": "error", "message": "Session not found."})
        if session_obj.tenant_id != tenant_uuid:
            return format_response({"action": "error", "message": "Session does not belong to this tenant."})

        await db.execute(delete(models.TransformationScenario).where(models.TransformationScenario.session_id == sid))
        await db.execute(delete(models.TransformationSession).where(models.TransformationSession.id == sid))
        await db.commit()

        return format_response({
            "action": "session_deleted",
            "message": f"Session {sid} has been deleted.",
            "session_id": str(sid),
        })

    # ────────────── HELP ──────────────
    if _match(text, [r'help', r'what\s+can\s+(?:you|i)', r'commands?', r'how\s+(?:do|to)']):
        return format_response({
            "action": "help",
            "message": "Here's what you can do from the Admin Command Center:",
            "commands": [
                {"category": "Model Versions", "examples": [
                    'Create a new model version called "Q1 2026 Strategy"',
                    "Show all model versions",
                    'Activate model version "Q1 2026 Strategy"',
                ]},
                {"category": "Rules", "examples": [
                    'Create a rule called "High Debt Warning" when technical_debt > 80 then set state_impact +15',
                    "Show all rules",
                    'Deactivate rule "High Debt Warning"',
                ]},
                {"category": "States & Thresholds", "examples": [
                    "Show state definitions",
                ]},
                {"category": "Monitoring", "examples": [
                    "Show platform overview",
                    "Show recent activity",
                    "Show audit logs",
                    "Show all sessions",
                    "Delete session <session-uuid>",
                ]},
            ],
        })

    # ────────────── FALLBACK ──────────────
    return format_response({
        "action": "unrecognized",
        "message": f'I didn\'t understand that command. Try things like:\n• "Show platform overview"\n• "Create a new model version called Q1 Strategy"\n• "Show all rules"\n• "Show audit logs"\n• Type "help" for full command list.',
    })


# ── Helper: NL condition to expression ───────────────────────────────────

def _normalize_metric_aliases(text: str) -> str:
    aliases = {
        r"\boperating\s+costs?\b": "cost",
        r"\bcosts?\b": "cost",
        r"\brevenues?\b": "revenue",
        r"\btech(?:nical)?\s+debt\b": "technical_debt",
        r"\bdebt\b": "technical_debt",
        r"\bprofit\s*margin\b": "margin",
    }
    out = text.lower()
    for pattern, replacement in aliases.items():
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    return out


def _num_str(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _parse_number(raw: str) -> float:
    cleaned = raw.replace(",", "").replace("$", "").replace("%", "").strip()
    return float(cleaned)


def _coerce_threshold(metric: str, raw_value: str, percent_word: bool = False) -> str:
    value = _parse_number(raw_value)
    if metric == "margin" and (percent_word or "%" in raw_value):
        value = value / 100.0
    return _num_str(value)


def _clause_to_expression(clause: str) -> str:
    c = _normalize_metric_aliases(clause.strip())

    comp_ops = [
        (">=", r"(?:>=|at\s+least|no\s+less\s+than|not\s+less\s+than)"),
        ("<=", r"(?:<=|at\s+most|no\s+more\s+than|not\s+more\s+than)"),
        (">", r"(?:>|greater\s+than|above|over|more\s+than|exceeds?|surpasses?)"),
        ("<", r"(?:<|less\s+than|below|under|falls?\s+below|drops?\s+below)"),
    ]

    # Example: cost greater than 75 percent of revenue -> cost > (revenue * 0.75)
    for op, op_pat in comp_ops:
        m = re.search(
            rf"\b([a-z_][a-z0-9_]*)\b\s*(?:(?:is|are)\s+)?{op_pat}\s*([\d.,]+)\s*(%|percent)?\s+of\s+\b([a-z_][a-z0-9_]*)\b",
            c,
            flags=re.IGNORECASE,
        )
        if m:
            left = m.group(1)
            pct = _parse_number(m.group(2))
            ratio = pct / 100.0
            right = m.group(4)
            return f"{left} {op} ({right} * {_num_str(ratio)})"

    # Example: margin between 10 and 20 percent
    m = re.search(
        r"\b([a-z_][a-z0-9_]*)\b\s+between\s+([\d.,]+)\s*(%|percent)?\s+and\s+([\d.,]+)\s*(%|percent)?",
        c,
        flags=re.IGNORECASE,
    )
    if m:
        metric = m.group(1)
        lower = _coerce_threshold(metric, m.group(2), percent_word=bool(m.group(3)))
        upper = _coerce_threshold(metric, m.group(4), percent_word=bool(m.group(5)))
        return f"({metric} >= {lower}) and ({metric} <= {upper})"

    # Example: margin below 12 percent / cost > 220
    for op, op_pat in comp_ops:
        m = re.search(
            rf"\b([a-z_][a-z0-9_]*)\b\s*(?:(?:is|are)\s+)?{op_pat}\s*([\d.,]+)\s*(%|percent)?",
            c,
            flags=re.IGNORECASE,
        )
        if m:
            metric = m.group(1)
            threshold = _coerce_threshold(metric, m.group(2), percent_word=bool(m.group(3)))
            return f"{metric} {op} {threshold}"

    return clause


def _nl_to_condition(text: str) -> str:
    """Convert natural language condition to deterministic engine expression."""
    normalized = _normalize_metric_aliases(text.strip())
    parts = re.split(r"\s+(and|or)\s+", normalized, flags=re.IGNORECASE)
    if len(parts) == 1:
        return _clause_to_expression(parts[0])

    expr_parts: List[str] = []
    i = 0
    while i < len(parts):
        token = parts[i].strip()
        if token.lower() in {"and", "or"}:
            expr_parts.append(token.lower())
        elif token:
            expr_parts.append(f"({_clause_to_expression(token)})")
        i += 1

    return " ".join(expr_parts) if expr_parts else text


def _nl_to_impact(text: str) -> str:
    """Convert natural language impact to engine impact expression."""
    t = text.lower().strip()

    m = re.search(r'(?:state[_\s]*impact|impact|score)\s*(?:to\s*)?([+-]?\s*[\d.]+)', t)
    if m:
        return m.group(1).replace(' ', '')

    m = re.search(r'(?:add|increase|boost)\s*(?:by\s*)?([\d.]+)', t)
    if m:
        return f"+{m.group(1)}"

    m = re.search(r'(?:reduce|decrease|subtract)\s*(?:by\s*)?([\d.]+)', t)
    if m:
        return f"-{m.group(1)}"

    m = re.search(r'([+-]?\d+(?:\.\d+)?)', t)
    if m:
        return m.group(1)

    return text


# ── Platform overview helper ─────────────────────────────────────────────

async def _platform_overview(db: AsyncSession, tenant_uuid: uuid.UUID) -> dict:
    """Gather platform statistics."""
    # Count model versions
    mv_res = await db.execute(
        select(func.count()).select_from(models.ModelVersion).where(models.ModelVersion.tenant_id == tenant_uuid)
    )
    mv_count = mv_res.scalar() or 0

    # Active model version (tenant-owned)
    amv_res = await db.execute(
        select(models.ModelVersion).where(
            models.ModelVersion.tenant_id == tenant_uuid,
            models.ModelVersion.is_active == True
        ).limit(1)
    )
    active_mv = amv_res.scalars().first()

    # Count rules (tenant-owned)
    rule_res = await db.execute(
        select(func.count()).select_from(models.Rule).where(models.Rule.tenant_id == tenant_uuid, models.Rule.is_active == True)
    )
    rule_count = rule_res.scalar() or 0

    # Count sessions
    sess_res = await db.execute(
        select(func.count()).select_from(models.TransformationSession).where(models.TransformationSession.tenant_id == tenant_uuid)
    )
    session_count = sess_res.scalar() or 0

    # Count state definitions
    state_res = await db.execute(
        select(func.count()).select_from(models.StateDefinition).where(models.StateDefinition.tenant_id == tenant_uuid)
    )
    state_count = state_res.scalar() or 0

    # Count audit events
    audit_res = await db.execute(
        select(func.count()).select_from(models.AuditLog).where(models.AuditLog.tenant_id == tenant_uuid)
    )
    audit_count = audit_res.scalar() or 0

    # Most recent activity
    recent_res = await db.execute(
        select(models.AuditLog)
        .where(models.AuditLog.tenant_id == tenant_uuid)
        .order_by(models.AuditLog.created_at.desc())
        .limit(5)
    )
    recent = recent_res.scalars().all()
    recent_items = [{
        "action": r.action,
        "actor": r.actor,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in recent]

    effective_mv = active_mv

    # Fallback for local/demo tenant mismatch: derive effective model from tenant sessions.
    if effective_mv is None:
        latest_session_q = (
            select(models.TransformationSession)
            .where(models.TransformationSession.tenant_id == tenant_uuid)
            .order_by(models.TransformationSession.created_at.desc())
            .limit(1)
        )
        latest_session_res = await db.execute(latest_session_q)
        latest_session = latest_session_res.scalars().first()
        if latest_session:
            effective_mv = await db.get(models.ModelVersion, latest_session.model_version_id)

    if mv_count == 0 and effective_mv is not None:
        mv_count = 1

    if rule_count == 0 and effective_mv is not None:
        effective_rule_res = await db.execute(
            select(func.count()).select_from(models.Rule).where(
                models.Rule.model_version_id == effective_mv.id,
                models.Rule.is_active == True,
            )
        )
        rule_count = effective_rule_res.scalar() or 0

    return format_response({
        "action": "platform_overview",
        "message": "Platform overview loaded.",
        "overview": {
            "model_versions": mv_count,
            "active_model_version": {
                "id": str(effective_mv.id) if effective_mv else None,
                "name": effective_mv.name if effective_mv else None,
            },
            "active_rules": rule_count,
            "sessions": session_count,
            "state_definitions": state_count,
            "audit_events": audit_count,
            "recent_activity": recent_items,
        },
    })
