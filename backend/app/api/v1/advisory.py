from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import json
import uuid
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import format_response
from app.db import models
from app.db.session import get_session
from app.services.engine import run_deterministic_engine

router = APIRouter()

RUNTIME_AGENTS_PATH = Path(__file__).resolve().parents[3] / "openclaw" / "agents" / "strategos_advisory_agents.runtime.json"

BOARD_TO_RUNTIME_AGENT = {
    "schema_extraction_agent": "strategos-schema-extraction",
    "strategy_advisor": "strategos-strategy-advisor",
    "risk_officer": "strategos-risk-officer",
    "architecture_advisor": "strategos-architecture-advisor",
    "financial_impact_advisor": "strategos-financial-impact-advisor",
    "synthesis_advisor": "strategos-synthesis-advisor",
}


def _load_board_agents() -> List[Dict[str, Any]]:
    try:
        board_path = Path(__file__).resolve().parents[3] / "openclaw" / "agents" / "strategos_advisory_board.json"
        payload = json.loads(board_path.read_text(encoding="utf-8"))
        agents = payload.get("agents")
        if isinstance(agents, list):
            return [a for a in agents if isinstance(a, dict)]
    except Exception:
        pass
    return []


def _load_runtime_agents() -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(RUNTIME_AGENTS_PATH.read_text(encoding="utf-8"))
        agents = payload.get("agents")
        if isinstance(agents, list):
            out: Dict[str, Dict[str, Any]] = {}
            for item in agents:
                if not isinstance(item, dict):
                    continue
                aid = item.get("id")
                if isinstance(aid, str) and aid.strip():
                    out[aid.strip()] = item
            return out
    except Exception:
        pass
    return {}


def _resolve_runtime_profile(agent_id: str, role: str) -> Tuple[str, str, str]:
    runtime_agents = _load_runtime_agents()
    runtime_id = BOARD_TO_RUNTIME_AGENT.get(agent_id)
    runtime_cfg = runtime_agents.get(runtime_id or "", {})

    model = str(runtime_cfg.get("model") or "").strip()
    role_prompt = str(runtime_cfg.get("role_prompt") or "").strip()
    if not role_prompt:
        role_prompt = (
            f"You are {role}. Produce concise, board-ready guidance using deterministic STRATEGOS artifacts only. "
            "Do not add unsupported deterministic claims."
        )
    return runtime_id or "", model, role_prompt


def _extract_snapshot_evidence(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = snapshot.get("state", "UNKNOWN")
    contributions = snapshot.get("contributions") or []
    restructuring = snapshot.get("restructuring_actions") or []
    triggered = [c.get("expression") for c in contributions if isinstance(c, dict) and c.get("result")]
    top_actions = [r.get("template_name") for r in restructuring if isinstance(r, dict)][:3]
    return {
        "state": state,
        "triggered_conditions": triggered,
        "restructuring_actions": top_actions,
    }


def _extract_openclaw_text(payload: Any) -> str:
    if payload is None:
        return ""

    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        candidate_keys = [
            "insight",
            "response",
            "output",
            "message",
            "content",
            "text",
        ]
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        data = payload.get("data")
        if isinstance(data, dict):
            nested = _extract_openclaw_text(data)
            if nested:
                return nested

        return json.dumps(payload)

    if isinstance(payload, list):
        if not payload:
            return ""
        return _extract_openclaw_text(payload[0])

    return str(payload).strip()


def _build_deterministic_fallback_insight(role: str, evidence: Dict[str, Any]) -> str:
    state = str(evidence.get("state") or "UNKNOWN")
    triggered = evidence.get("triggered_conditions") or []
    actions = evidence.get("restructuring_actions") or []

    triggered_text = ", ".join(str(x) for x in triggered[:3]) if triggered else "no triggered diagnostic conditions"
    action_text = ", ".join(str(x) for x in actions[:2]) if actions else "no restructuring actions returned"

    return (
        f"{role}: Deterministic advisory fallback generated from STRATEGOS snapshot. "
        f"Current state is {state}; key triggers: {triggered_text}; "
        f"recommended execution focus: {action_text}."
    )


async def _invoke_openclaw_remote(runtime_agent_id: str, user_message: str, timeout_sec: int) -> str:
    base_url = os.getenv("OPENCLAW_API_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="openclaw_api_base_url_missing")

    endpoint = os.getenv("OPENCLAW_API_AGENT_PATH", "/agent").strip()
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"

    token = os.getenv("OPENCLAW_API_AUTH_TOKEN", "").strip()
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "agent": runtime_agent_id,
        "message": user_message,
        "json": True,
    }

    request_timeout = float(os.getenv("OPENCLAW_API_TIMEOUT_SECONDS", str(timeout_sec)))

    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            res = await client.post(f"{base_url}{endpoint}", headers=headers, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"openclaw_remote_timeout: {runtime_agent_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"openclaw_remote_invoke_failed: {exc}")

    if res.status_code >= 400:
        detail = (res.text or "")[:1000]
        raise HTTPException(status_code=502, detail=f"openclaw_remote_error_{runtime_agent_id}: {detail}")

    try:
        body = res.json()
    except Exception:
        body = res.text

    content = _extract_openclaw_text(body)
    if not content:
        raise HTTPException(status_code=502, detail=f"openclaw_remote_empty_output: {runtime_agent_id}")

    try:
        maybe_json = json.loads(content)
        parsed_content = _extract_openclaw_text(maybe_json)
        if parsed_content:
            return parsed_content
    except Exception:
        pass

    return content


async def _invoke_openclaw_local_cli(runtime_agent_id: str, user_message: str, timeout_sec: int) -> str:
    openclaw_bin = os.getenv("OPENCLAW_BIN", "/home/ubuntu/.npm-global/bin/openclaw").strip()

    cmd = [
        openclaw_bin,
        "agent",
        "--agent",
        runtime_agent_id,
        "--message",
        user_message,
        "--json",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"openclaw_agent_timeout: {runtime_agent_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"openclaw_agent_invoke_failed: {exc}")

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[:1000]
        raise HTTPException(status_code=502, detail=f"openclaw_agent_error_{runtime_agent_id}: {err}")

    raw_output = (proc.stdout or "").strip()
    if not raw_output:
        raise HTTPException(status_code=502, detail=f"openclaw_agent_empty_output: {runtime_agent_id}")

    content = _extract_openclaw_text(raw_output)
    try:
        parsed = json.loads(content)
        content = _extract_openclaw_text(parsed) or content
    except Exception:
        pass

    if not content:
        raise HTTPException(status_code=502, detail=f"openclaw_agent_missing_insight: {runtime_agent_id}")

    return content


async def _build_agent_insight(agent_id: str, role: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    runtime_agent_id, model, role_prompt = _resolve_runtime_profile(agent_id, role)
    timeout_sec = int(os.getenv("OPENCLAW_AGENT_TIMEOUT_SECONDS", "90"))
    execution_mode = os.getenv("OPENCLAW_EXECUTION_MODE", "remote_http").strip().lower()
    allow_fallback = os.getenv("OPENCLAW_ALLOW_DETERMINISTIC_FALLBACK", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if runtime_agent_id == "":
        raise HTTPException(status_code=503, detail=f"runtime_agent_mapping_missing_for_{agent_id}")

    evidence = _extract_snapshot_evidence(snapshot)

    agent_payload = {
        "agent_id": agent_id,
        "runtime_agent_id": runtime_agent_id,
        "role": role,
        "model": model,
        "snapshot": {
            "state": snapshot.get("state"),
            "score_breakdown": snapshot.get("score_breakdown"),
            "scores": snapshot.get("scores"),
            "contributions": snapshot.get("contributions"),
            "restructuring_actions": snapshot.get("restructuring_actions"),
        },
        "instructions": [
            "Respond as this advisory agent only.",
            "Use deterministic artifacts only; do not invent deterministic values.",
            "Return strict JSON: {\"insight\": string}.",
        ],
    }

    user_message = (
        f"{role_prompt}\n\n"
        "Use only the deterministic STRATEGOS payload below.\n"
        "Return strict JSON with one key: insight.\n\n"
        f"{json.dumps(agent_payload)}"
    )

    insight_text = ""
    failure_detail = ""

    try:
        if execution_mode in {"remote_http", "remote", "http"}:
            insight_text = await _invoke_openclaw_remote(runtime_agent_id, user_message, timeout_sec)
        elif execution_mode in {"local_cli", "cli"}:
            insight_text = await _invoke_openclaw_local_cli(runtime_agent_id, user_message, timeout_sec)
        elif execution_mode in {"deterministic_fallback", "fallback"}:
            insight_text = _build_deterministic_fallback_insight(role, evidence)
        else:
            raise HTTPException(status_code=503, detail=f"unsupported_openclaw_execution_mode: {execution_mode}")
    except HTTPException as exc:
        failure_detail = str(exc.detail)
        if allow_fallback:
            insight_text = _build_deterministic_fallback_insight(role, evidence)
        else:
            raise

    if not insight_text:
        if allow_fallback:
            insight_text = _build_deterministic_fallback_insight(role, evidence)
        else:
            raise HTTPException(status_code=502, detail=f"openclaw_agent_missing_insight: {runtime_agent_id}")

    return {
        "agent_id": agent_id,
        "role": role,
        "insight": insight_text,
        "evidence": evidence,
        "source": execution_mode,
        "warning": failure_detail or None,
    }


class SkillCreateSessionRequest(BaseModel):
    tenant_id: str
    model_version_id: str
    name: Optional[str] = None


class SkillRunEngineRequest(BaseModel):
    tenant_id: Optional[str] = None
    model_version_id: Optional[str] = None
    session_id: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)


def _parse_snapshot_payload(raw_snapshot: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw_snapshot:
        return None
    try:
        payload = json.loads(raw_snapshot)
    except Exception:
        return None

    if isinstance(payload, dict) and isinstance(payload.get("latest"), dict):
        return payload.get("latest")
    if isinstance(payload, dict):
        return payload
    return None


def _append_snapshot_history(existing_raw: Optional[str], snapshot: Dict[str, Any]) -> str:
    existing_payload: Dict[str, Any] = {}
    if existing_raw:
        try:
            existing_payload = json.loads(existing_raw)
        except Exception:
            existing_payload = {
                "version": 0,
                "latest": None,
                "history": [],
                "legacy_snapshot": existing_raw,
            }

    old_version = int(existing_payload.get("version") or 0)
    new_version = old_version + 1
    old_history = existing_payload.get("history")
    if not isinstance(old_history, list):
        old_history = []

    event = {
        "version": new_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": snapshot,
    }
    packed = {
        "version": new_version,
        "latest": snapshot,
        "history": [*old_history, event],
    }
    return json.dumps(packed)


@router.post("/advisory/skills/create_session")
async def skill_create_session(payload: SkillCreateSessionRequest, db: AsyncSession = Depends(get_session)):
    try:
        tenant_id = uuid.UUID(payload.tenant_id)
        model_version_id = uuid.UUID(payload.model_version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_uuid_in_payload")

    stmt = (
        insert(models.TransformationSession)
        .values(
            tenant_id=tenant_id,
            model_version_id=model_version_id,
            name=payload.name,
        )
        .returning(models.TransformationSession.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    sid = res.scalar()
    return format_response({"session_id": str(sid)})


@router.post("/advisory/skills/run_engine")
async def skill_run_engine(payload: SkillRunEngineRequest, db: AsyncSession = Depends(get_session)):
    session_obj = None
    session_uuid = None
    if payload.session_id:
        try:
            session_uuid = uuid.UUID(payload.session_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_session_id")
        session_obj = await db.get(models.TransformationSession, session_uuid)
        if session_obj is None:
            raise HTTPException(status_code=404, detail="session_not_found")

    snapshot = await run_deterministic_engine(
        db,
        model_version_id=payload.model_version_id,
        input_data=payload.input,
    )

    # Audit event
    tenant_uuid = None
    for candidate in [
        payload.tenant_id,
        (snapshot.get("model_version") or {}).get("tenant_id") if isinstance(snapshot, dict) else None,
    ]:
        if not candidate:
            continue
        try:
            tenant_uuid = uuid.UUID(str(candidate))
            break
        except Exception:
            continue

    await db.execute(
        insert(models.AuditLog).values(
            tenant_id=tenant_uuid,
            actor="openclaw_skill",
            action="OPENCLAW_RUN_ENGINE",
            payload=json.dumps(
                {
                    "model_version_id": payload.model_version_id,
                    "session_id": payload.session_id,
                    "input": payload.input,
                    "state": snapshot.get("state") if isinstance(snapshot, dict) else None,
                    "total_score": (snapshot.get("score_breakdown") or {}).get("total_score") if isinstance(snapshot, dict) else None,
                    "error": snapshot.get("error") if isinstance(snapshot, dict) else None,
                }
            ),
        )
    )

    if payload.session_id and isinstance(snapshot, dict) and not snapshot.get("error"):
        packed = _append_snapshot_history(session_obj.snapshot if session_obj else None, snapshot)
        await db.execute(
            models.TransformationSession.__table__
            .update()
            .where(models.TransformationSession.id == session_uuid)
            .values(snapshot=packed)
        )

    await db.commit()

    if isinstance(snapshot, dict) and snapshot.get("error"):
        raise HTTPException(status_code=400, detail=snapshot)

    return format_response(
        {
            "session_id": payload.session_id,
            "state": snapshot.get("state") if isinstance(snapshot, dict) else None,
            "total_score": (snapshot.get("score_breakdown") or {}).get("total_score") if isinstance(snapshot, dict) else None,
            "snapshot": snapshot,
        }
    )


@router.get("/advisory/skills/state/{session_id}")
async def skill_fetch_state(session_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    latest = _parse_snapshot_payload(session_obj.snapshot)
    if not latest:
        raise HTTPException(status_code=404, detail="session_snapshot_not_found")

    return format_response(
        {
            "session_id": session_id,
            "state": latest.get("state"),
            "total_score": (latest.get("score_breakdown") or {}).get("total_score"),
        }
    )


@router.get("/advisory/skills/contributions/{session_id}")
async def skill_fetch_contributions(session_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    latest = _parse_snapshot_payload(session_obj.snapshot)
    if not latest:
        raise HTTPException(status_code=404, detail="session_snapshot_not_found")

    return format_response(
        {
            "session_id": session_id,
            "contributions": latest.get("contributions") or [],
            "scores": latest.get("scores") or {},
        }
    )


@router.get("/advisory/skills/restructuring/{session_id}")
async def skill_fetch_restructuring(session_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    latest = _parse_snapshot_payload(session_obj.snapshot)
    if not latest:
        raise HTTPException(status_code=404, detail="session_snapshot_not_found")

    return format_response(
        {
            "session_id": session_id,
            "state": latest.get("state"),
            "restructuring_actions": latest.get("restructuring_actions") or [],
        }
    )


@router.get("/advisory/skills/board_insights/{session_id}")
async def skill_board_insights(session_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    latest = _parse_snapshot_payload(session_obj.snapshot)
    if not latest:
        raise HTTPException(status_code=404, detail="session_snapshot_not_found")

    agents = _load_board_agents()
    insights = []
    for agent in agents:
        agent_id = str(agent.get("id") or "unknown_agent")
        role = str(agent.get("role") or "")
        insights.append(await _build_agent_insight(agent_id, role, latest))

    return format_response(
        {
            "session_id": session_id,
            "state": latest.get("state"),
            "insights": insights,
        }
    )


@router.get("/advisory/skills/model_versions")
async def skill_list_model_versions(
    tenant_id: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_session),
):
    q = select(models.ModelVersion)
    if tenant_id:
        try:
            tid = uuid.UUID(tenant_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_tenant_id")
        q = q.where(models.ModelVersion.tenant_id == tid)
    if active_only:
        q = q.where(models.ModelVersion.is_active == True)

    res = await db.execute(q)
    rows = res.scalars().all()
    return format_response(
        {
            "model_versions": [
                {
                    "id": str(mv.id),
                    "tenant_id": str(mv.tenant_id),
                    "name": mv.name,
                    "description": mv.description,
                    "is_active": bool(mv.is_active),
                }
                for mv in rows
            ]
        }
    )


@router.get("/advisory/skills/show_rules")
async def skill_show_rules(
    model_version_id: str = Query(...),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_session),
):
    try:
        mv = uuid.UUID(model_version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_model_version_id")

    q = select(models.Rule).where(models.Rule.model_version_id == mv)
    if active_only:
        q = q.where(models.Rule.is_active == True)
    res = await db.execute(q)
    rules = res.scalars().all()

    out: List[Dict[str, Any]] = []
    for rule in rules:
        cond_q = select(models.RuleCondition).where(models.RuleCondition.rule_id == rule.id)
        imp_q = select(models.RuleImpact).where(models.RuleImpact.rule_id == rule.id)
        cond_res = await db.execute(cond_q)
        imp_res = await db.execute(imp_q)
        conditions = cond_res.scalars().all()
        impacts = imp_res.scalars().all()

        out.append(
            {
                "id": str(rule.id),
                "name": rule.name,
                "description": rule.description,
                "is_active": bool(rule.is_active),
                "conditions": [
                    {"id": str(c.id), "expression": c.expression, "is_active": bool(c.is_active)}
                    for c in conditions
                ],
                "impacts": [
                    {"id": str(i.id), "impact": i.impact, "is_active": bool(i.is_active)}
                    for i in impacts
                ],
            }
        )

    return format_response({"rules": out})
