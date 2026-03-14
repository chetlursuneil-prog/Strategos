from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import asyncio
import json
import uuid
import os
import subprocess
import re
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import websockets

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

AGENT_CHAIN_ORDER = [
    "schema_extraction_agent",
    "strategy_advisor",
    "architecture_advisor",
    "risk_officer",
    "financial_impact_advisor",
    "synthesis_advisor",
]

FLOW_VERSION = "v1.0-cumulative-chain"

CHAIN_HANDOVER_TEMPLATES = {
    "schema_extraction_agent": (
        "You are the Catalyst. Transform the CEO goal into a high-level strategic framework. "
        "Focus on the What and the Why."
    ),
    "strategy_advisor": (
        "You are the Refiner. Review the strategic framework and refine it using market positioning "
        "and competitive edge. Add depth to the How without changing the What."
    ),
    "architecture_advisor": (
        "You are the Blueprint. Based on the refined strategy, propose architecture and execution structure. "
        "Identify build-vs-buy and structural requirements."
    ),
    "risk_officer": (
        "You are the Reality Check. Review strategy and architecture and identify top 3-5 risks. "
        "For each risk provide explicit mitigation."
    ),
    "financial_impact_advisor": (
        "You are the Bottom Line. Quantify ROI and budget impact considering architecture and risk mitigations. "
        "Provide CAPEX/OPEX split and payback period estimate."
    ),
    "synthesis_advisor": (
        "You are the Chief of Staff. Synthesize all prior outputs into a 3-paragraph CEO memo with "
        "Recommendation (Go/No-Go), Logic, and Ask."
    ),
}

STEP_REQUIRED_FIELDS = {
    "schema_extraction_agent": ["insight", "strategic_framework", "assumptions", "evidence_used", "confidence"],
    "strategy_advisor": ["insight", "strategic_narrative", "assumptions", "evidence_used", "confidence"],
    "architecture_advisor": ["insight", "architecture_blueprint", "assumptions", "evidence_used", "confidence"],
    "risk_officer": ["insight", "risk_register", "assumptions", "evidence_used", "confidence"],
    "financial_impact_advisor": ["insight", "financial_forecast", "assumptions", "evidence_used", "confidence"],
    "synthesis_advisor": ["insight", "executive_memo", "assumptions", "evidence_used", "confidence"],
}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


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


def _board_role_lookup() -> Dict[str, str]:
    roles: Dict[str, str] = {}
    for agent in _load_board_agents():
        aid = str(agent.get("id") or "").strip()
        role = str(agent.get("role") or "").strip()
        if aid:
            roles[aid] = role
    return roles


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


def _to_plain_rule(expression: str) -> str:
    mapping = {
        "margin < 0.12": "Operating margin is below 12%",
        "technical_debt > 65": "Technical debt is above 65%",
        "cost > (revenue * 0.82)": "Operating costs exceed 82% of revenue",
        "revenue_growth_yoy_pct < 3": "Revenue growth is below 3% YoY",
        "customer_churn_pct > 2.8": "Customer churn is above 2.8%",
        "(lead_time_days > 14) or (change_failure_rate_pct > 20)": "Lead time is above 14 days or change failure rate is above 20%",
        "p1_incidents_per_month > 5": "P1 incidents exceed 5 per month",
        "(cyber_findings_open_high > 10) or (regulatory_findings_open > 5)": "High cyber findings exceed 10 or regulatory findings exceed 5",
        "critical_role_attrition_pct > 12": "Critical-role attrition is above 12%",
        "(vendor_concentration_pct > 50) or (top_customer_concentration_pct > 40)": "Vendor concentration exceeds 50% or top-customer concentration exceeds 40%",
        "(cloud_adoption_pct < 40) and (automation_coverage_pct < 40)": "Cloud adoption is below 40% and automation coverage is below 40%",
        "cash_conversion_cycle_days > 80": "Cash conversion cycle exceeds 80 days",
    }
    raw = (expression or "").strip()
    return mapping.get(raw, raw)


def _top_coefficients(snapshot: Dict[str, Any], limit: int = 8) -> List[Dict[str, Any]]:
    score_breakdown = snapshot.get("score_breakdown") if isinstance(snapshot, dict) else {}
    if not isinstance(score_breakdown, dict):
        return []
    coefficient_items = score_breakdown.get("coefficient_contributions")
    if not isinstance(coefficient_items, list):
        return []
    sortable: List[Tuple[float, Dict[str, Any]]] = []
    for raw in coefficient_items:
        if not isinstance(raw, dict):
            continue
        try:
            contribution = float(raw.get("contribution") or 0.0)
        except Exception:
            contribution = 0.0
        sortable.append(
            (
                abs(contribution),
                {
                    "name": str(raw.get("name") or "coefficient"),
                    "contribution": contribution,
                    "error": raw.get("error"),
                },
            )
        )
    sortable.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in sortable[:limit]]


def _extract_openclaw_text(payload: Any) -> str:
    if payload is None:
        return ""

    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        # Common OpenClaw CLI / gateway envelopes:
        # {"result":{"payloads":[{"text":"..."}]}} or {"payloads":[...]}
        has_result = "result" in payload
        result = payload.get("result")
        if isinstance(result, (dict, list, str)):
            nested = _extract_openclaw_text(result)
            if nested:
                return nested

        has_payloads = "payloads" in payload
        payloads = payload.get("payloads")
        if isinstance(payloads, list):
            for item in payloads:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
                nested = _extract_openclaw_text(item)
                if nested:
                    return nested
            if has_payloads:
                return ""

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

        if has_payloads or has_result:
            return ""

        return json.dumps(payload)

    if isinstance(payload, list):
        if not payload:
            return ""
        for item in payload:
            nested = _extract_openclaw_text(item)
            if nested:
                return nested
        return ""

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
        "timeout": max(10, int(timeout_sec)),
    }

    request_timeout = float(os.getenv("OPENCLAW_API_TIMEOUT_SECONDS", "8"))
    if request_timeout <= 0:
        request_timeout = min(float(timeout_sec), 8.0)

    timeout_config = httpx.Timeout(
        timeout=request_timeout,
        connect=min(request_timeout, 5.0),
        read=request_timeout,
        write=min(request_timeout, 5.0),
        pool=min(request_timeout, 5.0),
    )

    parsed = urlparse(base_url)
    enable_ws_fallback = _env_flag("OPENCLAW_ENABLE_WS_FALLBACK", default=False)
    ws_url = ""
    if parsed.scheme in {"ws", "wss"}:
        ws_url = base_url
    elif enable_ws_fallback and parsed.scheme in {"http", "https"}:
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = urlunparse((ws_scheme, parsed.netloc, parsed.path or "", "", "", ""))

    if ws_url:
        try:
            return await _invoke_openclaw_ws(ws_url, headers, payload, request_timeout)
        except HTTPException:
            # Continue to HTTP compatibility fallback below.
            pass

    try:
        async with httpx.AsyncClient(timeout=timeout_config, trust_env=False) as client:
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


async def _invoke_openclaw_ws(ws_url: str, headers: Dict[str, str], payload: Dict[str, Any], request_timeout: float) -> str:
    # OpenClaw Gateway RPC protocol:
    # 1) receive connect.challenge event
    # 2) send connect request (type=req, method=connect)
    # 3) send agent method request (typically method=agent)
    # 4) consume matching response frame
    token = os.getenv("OPENCLAW_API_AUTH_TOKEN", "").strip()
    client_id = os.getenv("OPENCLAW_WS_CLIENT_ID", "cli").strip() or "cli"
    client_mode = os.getenv("OPENCLAW_WS_CLIENT_MODE", "cli").strip() or "cli"
    role = os.getenv("OPENCLAW_WS_ROLE", "operator").strip() or "operator"
    raw_scopes = os.getenv(
        "OPENCLAW_WS_SCOPES",
        "operator.admin,operator.approvals,operator.pairing,operator.read,operator.write",
    )
    scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()]
    agent_method = os.getenv("OPENCLAW_WS_AGENT_METHOD", "agent").strip() or "agent"
    origin = os.getenv("OPENCLAW_WS_ORIGIN", "").strip()

    ws_headers: Dict[str, str] = {}
    if origin:
        ws_headers["Origin"] = origin

    async def _recv_json(ws: Any, timeout: float) -> Dict[str, Any]:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        try:
            obj = json.loads(raw)
        except Exception:
            raise HTTPException(status_code=502, detail="openclaw_ws_invalid_json")
        if not isinstance(obj, dict):
            raise HTTPException(status_code=502, detail="openclaw_ws_invalid_frame")
        return obj

    async def _request(ws: Any, method: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        req_id = str(uuid.uuid4())
        req = {"type": "req", "id": req_id, "method": method, "params": params}
        await asyncio.wait_for(ws.send(json.dumps(req)), timeout=timeout)
        while True:
            frame = await _recv_json(ws, timeout)
            if frame.get("type") != "res":
                continue
            if frame.get("id") != req_id:
                continue
            return frame

    try:
        # websockets>=15 uses additional_headers; keep a fallback for older versions.
        try:
            ws = await websockets.connect(ws_url, additional_headers=ws_headers, open_timeout=request_timeout)
        except TypeError:
            ws = await websockets.connect(ws_url, extra_headers=list(ws_headers.items()), open_timeout=request_timeout)

        async with ws:
            first = await _recv_json(ws, request_timeout)
            if first.get("type") != "event" or first.get("event") != "connect.challenge":
                raise HTTPException(status_code=502, detail="openclaw_ws_missing_connect_challenge")

            connect_params: Dict[str, Any] = {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": client_id,
                    "version": "strategos-backend",
                    "platform": "python",
                    "mode": client_mode,
                },
                "role": role,
                "scopes": scopes,
                "caps": [],
            }
            if token:
                connect_params["auth"] = {"token": token}

            connect_res = await _request(ws, "connect", connect_params, request_timeout)
            if not bool(connect_res.get("ok")):
                err = (connect_res.get("error") or {}).get("message") or "connect_failed"
                raise HTTPException(status_code=502, detail=f"openclaw_ws_connect_failed: {err}")

            # New OpenClaw gateway exposes "agent". Some installations still expose
            # "agent.exec"; method is env-configurable.
            agent_res = await _request(ws, agent_method, payload, request_timeout)
            if not bool(agent_res.get("ok")):
                err = (agent_res.get("error") or {}).get("message") or "agent_method_failed"
                raise HTTPException(status_code=502, detail=f"openclaw_ws_agent_failed: {err}")
            body = agent_res.get("payload")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"openclaw_ws_timeout: {payload.get('agent')}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"openclaw_ws_invoke_failed: {exc}")

    # common response shapes: direct payload, {result: ...}, {body: ...}, {data: ...}
    if isinstance(body, dict):
        if "result" in body:
            return _extract_openclaw_text(body["result"])
        if "body" in body:
            return _extract_openclaw_text(body["body"])
        if "data" in body:
            return _extract_openclaw_text(body["data"])

    return _extract_openclaw_text(body)


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


def _is_retryable_remote_error(detail: str) -> bool:
    lowered = (detail or "").lower()
    retry_markers = [
        "504 gateway time-out",
        "gateway time-out",
        "openclaw_remote_timeout",
        "openclaw_ws_timeout",
        "bridge_timeout",
        "rate limit",
        "rate_limited",
        "connection reset",
        "temporarily unavailable",
    ]
    return any(marker in lowered for marker in retry_markers)


def _extract_first_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    text = (raw_text or "").strip()
    if not text:
        return None
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            loaded = json.loads(candidate)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            loaded = json.loads(candidate)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return None


def _normalize_text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _build_fixed_strategos_context(snapshot: Dict[str, Any], intake_ctx: Dict[str, Any]) -> Dict[str, Any]:
    score_breakdown = snapshot.get("score_breakdown") if isinstance(snapshot, dict) else {}
    if not isinstance(score_breakdown, dict):
        score_breakdown = {}
    contributions = snapshot.get("contributions") if isinstance(snapshot, dict) else []
    if not isinstance(contributions, list):
        contributions = []
    triggered_rules = [
        {
            "expression": str(c.get("expression") or ""),
            "plain_text": _to_plain_rule(str(c.get("expression") or "")),
        }
        for c in contributions
        if isinstance(c, dict) and bool(c.get("result"))
    ]
    return {
        "session_id": str(intake_ctx.get("session_id") or ""),
        "state": snapshot.get("state"),
        "scores": {
            "total_score": score_breakdown.get("total_score"),
            "state_score": score_breakdown.get("state_score"),
            "weighted_input_score": score_breakdown.get("weighted_input_score"),
            "rule_impact_score": score_breakdown.get("rule_impact_score"),
        },
        "triggered_rules": triggered_rules,
        "top_coefficient_contributions": _top_coefficients(snapshot),
        "restructuring_actions": snapshot.get("restructuring_actions") or [],
        "normalized_input_metrics": intake_ctx.get("input") or {},
        "metric_source": intake_ctx.get("metric_source") or {},
        "assumption_profile": intake_ctx.get("assumption_profile"),
    }


async def _load_session_intake_context(session_id: str, db: AsyncSession) -> Dict[str, Any]:
    # Intake data (original prompt, parsed metrics, sources) is stored in ENGINE_RUN audit payload.
    q = (
        select(models.AuditLog)
        .where(models.AuditLog.action == "ENGINE_RUN")
        .order_by(models.AuditLog.created_at.desc())
        .limit(500)
    )
    res = await db.execute(q)
    rows = res.scalars().all()
    for row in rows:
        payload_raw = row.payload
        if not payload_raw:
            continue
        try:
            payload = json.loads(payload_raw)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("session_id") or "") != session_id:
            continue
        return {
            "session_id": session_id,
            "ceo_request": str(payload.get("original_text") or ""),
            "input": payload.get("input") if isinstance(payload.get("input"), dict) else {},
            "metric_source": payload.get("metric_source") if isinstance(payload.get("metric_source"), dict) else {},
            "assumption_profile": payload.get("assumption_profile"),
        }
    return {
        "session_id": session_id,
        "ceo_request": "",
        "input": {},
        "metric_source": {},
        "assumption_profile": None,
    }


def _build_step_inputs(step_id: str, ceo_request: str, fixed_context: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _clip(value: Any, max_len: int = 320) -> str:
        text = str(value or "").strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."

    def _compact_context(src: Dict[str, Any]) -> Dict[str, Any]:
        scores = src.get("scores") if isinstance(src, dict) else {}
        if not isinstance(scores, dict):
            scores = {}
        metrics = src.get("normalized_input_metrics") if isinstance(src, dict) else {}
        if not isinstance(metrics, dict):
            metrics = {}
        triggered = src.get("triggered_rules") if isinstance(src, dict) else []
        if not isinstance(triggered, list):
            triggered = []
        coeffs = src.get("top_coefficient_contributions") if isinstance(src, dict) else []
        if not isinstance(coeffs, list):
            coeffs = []
        return {
            "state": src.get("state"),
            "scores": {
                "total_score": scores.get("total_score"),
                "state_score": scores.get("state_score"),
            },
            "assumption_profile": src.get("assumption_profile"),
            "key_metrics": {
                "revenue": metrics.get("revenue"),
                "cost": metrics.get("cost"),
                "margin": metrics.get("margin"),
                "technical_debt": metrics.get("technical_debt"),
            },
            "triggered_rules": [
                _clip((r.get("plain_text") if isinstance(r, dict) else r), 120) for r in triggered[:4]
            ],
            "top_coefficients": [
                {
                    "name": str(c.get("name") if isinstance(c, dict) else ""),
                    "contribution": c.get("contribution") if isinstance(c, dict) else None,
                }
                for c in coeffs[:4]
            ],
        }

    def _history_compact(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in items[:6]:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "agent_id": str(item.get("agent_id") or ""),
                    "summary": _clip(
                        (item.get("structured_output") or {}).get("summary")
                        or item.get("insight")
                        or item.get("raw_output_preview"),
                        220,
                    ),
                }
            )
        return out

    compact_context = _compact_context(fixed_context)
    by_id = {item.get("agent_id"): item for item in history if isinstance(item, dict)}
    if step_id == "schema_extraction_agent":
        return {
            "ceo_request": _clip(ceo_request, 420),
            "deterministic_context": compact_context,
        }
    if step_id == "strategy_advisor":
        return {
            "ceo_request_summary": _clip(
                (by_id.get("schema_extraction_agent") or {}).get("structured_output", {}).get("summary")
                or (by_id.get("schema_extraction_agent") or {}).get("insight")
                or ceo_request,
                280,
            ),
            "schema_extraction_output": _clip((by_id.get("schema_extraction_agent") or {}).get("insight"), 320),
            "deterministic_context": compact_context,
        }
    if step_id == "architecture_advisor":
        return {
            "strategy_output": _clip((by_id.get("strategy_advisor") or {}).get("insight"), 320),
            "deterministic_context": compact_context,
        }
    if step_id == "risk_officer":
        return {
            "strategy_output": _clip((by_id.get("strategy_advisor") or {}).get("insight"), 260),
            "architecture_output": _clip((by_id.get("architecture_advisor") or {}).get("insight"), 260),
            "deterministic_context": compact_context,
        }
    if step_id == "financial_impact_advisor":
        return {
            "architecture_output": _clip((by_id.get("architecture_advisor") or {}).get("insight"), 260),
            "risk_output": _clip((by_id.get("risk_officer") or {}).get("insight"), 260),
            "deterministic_context": compact_context,
        }
    # synthesis_advisor
    return {
        "full_history": _history_compact(history),
        "deterministic_context": compact_context,
    }


def _build_output_contract(step_id: str) -> Dict[str, Any]:
    contract = {
        "common_required": ["insight", "summary", "assumptions", "evidence_used", "confidence"],
        "step_required": STEP_REQUIRED_FIELDS.get(step_id, []),
        "confidence_enum": ["low", "medium", "high"],
    }
    if step_id == "synthesis_advisor":
        contract["executive_memo_required"] = ["recommendation", "logic", "ask"]
    return contract


def _validate_step_output(step_id: str, payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = STEP_REQUIRED_FIELDS.get(step_id, [])
    for key in required:
        if key not in payload:
            errors.append(f"missing_required_field:{key}")

    confidence = str(payload.get("confidence") or "").lower()
    if confidence and confidence not in {"low", "medium", "high"}:
        errors.append("invalid_confidence")

    assumptions = payload.get("assumptions")
    evidence_used = payload.get("evidence_used")
    if assumptions is not None and not isinstance(assumptions, list):
        errors.append("assumptions_not_list")
    if evidence_used is not None and not isinstance(evidence_used, list):
        errors.append("evidence_used_not_list")

    if step_id == "synthesis_advisor":
        memo = payload.get("executive_memo")
        if not isinstance(memo, dict):
            errors.append("executive_memo_missing_or_invalid")
        else:
            for mk in ["recommendation", "logic", "ask"]:
                if not isinstance(memo.get(mk), str) or not str(memo.get(mk)).strip():
                    errors.append(f"executive_memo_missing_{mk}")
    return errors


def _fallback_structured_output(step_id: str, role: str, fixed_context: Dict[str, Any], handoff_inputs: Dict[str, Any], reason: str) -> Dict[str, Any]:
    state = str(fixed_context.get("state") or "UNKNOWN")
    triggered = fixed_context.get("triggered_rules") or []
    top_trigger = triggered[0]["plain_text"] if isinstance(triggered, list) and triggered else "No triggered diagnostic rule"
    base = {
        "insight": f"{role}: Deterministic fallback used. State={state}. Key trigger: {top_trigger}.",
        "summary": f"Fallback summary for {role} from deterministic STRATEGOS context.",
        "assumptions": [f"Generated in fallback mode due: {reason}"],
        "evidence_used": [top_trigger],
        "confidence": "medium",
    }
    if step_id == "schema_extraction_agent":
        base["strategic_framework"] = {
            "objective": "Stabilize and improve enterprise posture based on deterministic diagnostics.",
            "why_now": f"Current deterministic state is {state}.",
            "priority_themes": ["margin discipline", "technical debt control", "execution reliability"],
        }
    elif step_id == "strategy_advisor":
        base["strategic_narrative"] = {
            "positioning": "Risk-aware modernization strategy",
            "strategic_moves": ["protect margin", "reduce debt drag", "improve operating rhythm"],
        }
    elif step_id == "architecture_advisor":
        base["architecture_blueprint"] = {
            "feasibility": "Feasible with staged execution",
            "build_vs_buy": "Hybrid",
            "structural_requirements": ["platform modernization", "automation uplift", "operating model governance"],
        }
    elif step_id == "risk_officer":
        base["risk_register"] = [
            {"risk": "Margin pressure", "mitigation": "Cost optimization and pricing governance"},
            {"risk": "Technical debt", "mitigation": "Debt burn-down roadmap with quarterly milestones"},
            {"risk": "Execution drift", "mitigation": "Stage-gate governance and KPI control tower"},
        ]
    elif step_id == "financial_impact_advisor":
        base["financial_forecast"] = {
            "capex_opex_split": {"capex_pct": 40, "opex_pct": 60},
            "roi_estimate": "Moderate positive ROI under staged execution",
            "payback_period_months": 18,
        }
    else:
        base["executive_memo"] = {
            "recommendation": "Go with staged controls",
            "logic": "Deterministic indicators show elevated pressure but manageable execution path with mitigations.",
            "ask": "Approve a phased transformation budget and governance cadence for the next 2 quarters.",
        }
    return base


def _coerce_non_json_step_output(
    step_id: str,
    role: str,
    fixed_context: Dict[str, Any],
    handoff_inputs: Dict[str, Any],
    raw_text: str,
) -> Dict[str, Any]:
    # Preserve live agent contribution text while still returning a schema-valid payload.
    # This avoids dropping to deterministic fallback when the model returns plain text.
    cleaned = str(raw_text or "").strip()
    if not cleaned:
        cleaned = f"{role}: non-JSON output with empty body."
    if len(cleaned) > 4000:
        cleaned = cleaned[:4000].rstrip() + " ..."

    coerced = _fallback_structured_output(
        step_id=step_id,
        role=role,
        fixed_context=fixed_context,
        handoff_inputs=handoff_inputs,
        reason="non_json_output",
    )
    coerced["insight"] = cleaned
    coerced["summary"] = cleaned[:600]
    assumptions = _normalize_text_list(coerced.get("assumptions"))
    coerced["assumptions"] = [
        "Output was non-JSON; Strategos applied schema coercion to preserve agent content.",
        *assumptions,
    ]
    return coerced


def _coerce_schema_invalid_step_output(
    step_id: str,
    role: str,
    fixed_context: Dict[str, Any],
    handoff_inputs: Dict[str, Any],
    raw_payload: Dict[str, Any],
    validation_errors: List[str],
) -> Dict[str, Any]:
    coerced = _fallback_structured_output(
        step_id=step_id,
        role=role,
        fixed_context=fixed_context,
        handoff_inputs=handoff_inputs,
        reason="schema_validation_failed",
    )

    if isinstance(raw_payload, dict):
        for key, value in raw_payload.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            coerced[key] = value

    extracted_text = _extract_openclaw_text(raw_payload)
    if isinstance(extracted_text, str) and extracted_text.strip():
        if not isinstance(coerced.get("insight"), str) or "Deterministic fallback used" in str(coerced.get("insight")):
            coerced["insight"] = extracted_text.strip()
        if not isinstance(coerced.get("summary"), str) or "Fallback summary" in str(coerced.get("summary")):
            coerced["summary"] = extracted_text.strip()[:600]

    if not isinstance(coerced.get("assumptions"), list):
        coerced["assumptions"] = _normalize_text_list(coerced.get("assumptions"))
    if not isinstance(coerced.get("evidence_used"), list):
        coerced["evidence_used"] = _normalize_text_list(coerced.get("evidence_used"))
    if not isinstance(coerced.get("insight"), str) or not str(coerced.get("insight")).strip():
        coerced["insight"] = "Schema-coerced advisory output."
    if not isinstance(coerced.get("summary"), str) or not str(coerced.get("summary")).strip():
        coerced["summary"] = str(coerced.get("insight"))[:600]

    assumptions = _normalize_text_list(coerced.get("assumptions"))
    coerced["assumptions"] = [
        f"Output schema was incomplete; Strategos coerced fields ({';'.join(validation_errors)}).",
        *assumptions,
    ]
    return coerced


async def _invoke_agent_text(runtime_agent_id: str, user_message: str, timeout_sec: int) -> str:
    execution_mode = os.getenv("OPENCLAW_EXECUTION_MODE", "remote_http").strip().lower()
    if execution_mode in {"remote_http", "remote", "http"}:
        return await _invoke_openclaw_remote(runtime_agent_id, user_message, timeout_sec)
    if execution_mode in {"local_cli", "cli"}:
        return await _invoke_openclaw_local_cli(runtime_agent_id, user_message, timeout_sec)
    raise HTTPException(status_code=503, detail=f"unsupported_openclaw_execution_mode: {execution_mode}")


async def _run_chain_step(
    step_id: str,
    role: str,
    step_index: int,
    ceo_request: str,
    snapshot: Dict[str, Any],
    fixed_context: Dict[str, Any],
    history: List[Dict[str, Any]],
    trace_id: str,
) -> Dict[str, Any]:
    runtime_agent_id, model, role_prompt = _resolve_runtime_profile(step_id, role)
    if runtime_agent_id == "":
        raise HTTPException(status_code=503, detail=f"runtime_agent_mapping_missing_for_{step_id}")

    timeout_sec = int(os.getenv("OPENCLAW_AGENT_TIMEOUT_SECONDS", "120"))
    allow_fallback = _env_flag("OPENCLAW_ALLOW_DETERMINISTIC_FALLBACK", default=True)
    remote_retries = _env_int("OPENCLAW_REMOTE_RETRIES", default=0, minimum=0, maximum=5)
    execution_mode = os.getenv("OPENCLAW_EXECUTION_MODE", "remote_http").strip().lower()

    handoff_inputs = _build_step_inputs(step_id, ceo_request, fixed_context, history)
    output_contract = _build_output_contract(step_id)
    handover_template = CHAIN_HANDOVER_TEMPLATES.get(step_id, "")

    chain_payload = {
        "flow_version": FLOW_VERSION,
        "trace_id": trace_id,
        "step": {"index": step_index, "id": step_id, "role": role},
        "handover_template": handover_template,
        "fixed_strategos_context": fixed_context,
        "handoff_inputs": handoff_inputs,
        "output_contract": output_contract,
    }

    user_message = (
        f"{role_prompt}\n\n"
        f"{handover_template}\n\n"
        "You must return strict JSON only (no markdown fences, no additional commentary).\n"
        f"Use this exact output contract: {json.dumps(output_contract)}\n\n"
        f"{json.dumps(chain_payload)}"
    )

    started = time.perf_counter()
    retries_used = 0
    warning: Optional[str] = None
    used_fallback = False
    raw_text = ""
    structured: Dict[str, Any] = {}
    source = execution_mode

    while True:
        try:
            if execution_mode in {"deterministic_fallback", "fallback"}:
                raise HTTPException(status_code=503, detail=f"step_forced_fallback:{step_id}")

            raw_text = await _invoke_agent_text(runtime_agent_id, user_message, timeout_sec)
            lowered = (raw_text or "").lower()
            if "rate limit" in lowered or "try again later" in lowered:
                raise HTTPException(status_code=502, detail=f"openclaw_remote_rate_limited:{step_id}")
            maybe_json = _extract_first_json_object(raw_text)
            if not isinstance(maybe_json, dict):
                structured = _coerce_non_json_step_output(step_id, role, fixed_context, handoff_inputs, raw_text)
                warning = f"step_non_json_coerced:{step_id}"
                break
            structured = maybe_json
            validation_errors = _validate_step_output(step_id, structured)
            if validation_errors:
                structured = _coerce_schema_invalid_step_output(
                    step_id=step_id,
                    role=role,
                    fixed_context=fixed_context,
                    handoff_inputs=handoff_inputs,
                    raw_payload=structured,
                    validation_errors=validation_errors,
                )
                warning = f"step_schema_coerced:{';'.join(validation_errors)}"
            break
        except HTTPException as exc:
            detail = str(exc.detail)
            should_retry = (
                execution_mode in {"remote_http", "remote", "http"}
                and retries_used < remote_retries
                and _is_retryable_remote_error(detail)
            )
            if should_retry:
                retries_used += 1
                await asyncio.sleep(min(1.25 * retries_used, 4.0))
                continue
            if not allow_fallback:
                raise
            used_fallback = True
            warning = detail
            source = "deterministic_fallback"
            structured = _fallback_structured_output(step_id, role, fixed_context, handoff_inputs, detail)
            raw_text = json.dumps(structured)
            break

    latency_ms = int((time.perf_counter() - started) * 1000)
    insight_text = str(structured.get("insight") or "").strip() or _build_deterministic_fallback_insight(role, _extract_snapshot_evidence(snapshot))

    return {
        "agent_id": step_id,
        "runtime_agent_id": runtime_agent_id,
        "role": role,
        "step_index": step_index,
        "model": model,
        "source": source,
        "used_fallback": used_fallback,
        "warning": warning,
        "latency_ms": latency_ms,
        "retries_used": retries_used,
        "input_agent_ids": [str(item.get("agent_id") or "") for item in history],
        "insight": insight_text,
        "structured_output": structured,
        "raw_output_preview": raw_text[:1000],
    }


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
    score_breakdown = snapshot.get("score_breakdown") if isinstance(snapshot, dict) else {}
    if not isinstance(score_breakdown, dict):
        score_breakdown = {}
    coefficient_items = score_breakdown.get("coefficient_contributions")
    if not isinstance(coefficient_items, list):
        coefficient_items = []

    compact_coefficients: List[Dict[str, Any]] = []
    sortable_coefficients: List[Tuple[float, Dict[str, Any]]] = []
    for raw in coefficient_items:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "coefficient")
        contribution = raw.get("contribution")
        error = raw.get("error")
        try:
            numeric_contribution = float(contribution)
        except Exception:
            numeric_contribution = 0.0
        item = {
            "name": name,
            "contribution": numeric_contribution,
            "error": error,
        }
        sortable_coefficients.append((abs(numeric_contribution), item))

    if sortable_coefficients:
        sortable_coefficients.sort(key=lambda pair: pair[0], reverse=True)
        compact_coefficients = [item for _, item in sortable_coefficients[:8]]

    agent_payload = {
        "agent_id": agent_id,
        "runtime_agent_id": runtime_agent_id,
        "role": role,
        "model": model,
        "deterministic_summary": {
            "state": snapshot.get("state"),
            "total_score": score_breakdown.get("total_score"),
            "state_score": score_breakdown.get("state_score"),
            "weighted_input_score": score_breakdown.get("weighted_input_score"),
            "rule_impact_score": score_breakdown.get("rule_impact_score"),
            "triggered_conditions": evidence.get("triggered_conditions") or [],
            "restructuring_actions": evidence.get("restructuring_actions") or [],
            "top_coefficient_contributions": compact_coefficients,
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
    remote_retries = _env_int("OPENCLAW_REMOTE_RETRIES", default=0, minimum=0, maximum=5)
    attempt = 0

    while True:
        try:
            if execution_mode in {"remote_http", "remote", "http"}:
                insight_text = await _invoke_openclaw_remote(runtime_agent_id, user_message, timeout_sec)
            elif execution_mode in {"local_cli", "cli"}:
                insight_text = await _invoke_openclaw_local_cli(runtime_agent_id, user_message, timeout_sec)
            elif execution_mode in {"deterministic_fallback", "fallback"}:
                insight_text = _build_deterministic_fallback_insight(role, evidence)
            else:
                raise HTTPException(status_code=503, detail=f"unsupported_openclaw_execution_mode: {execution_mode}")

            lowered_insight = (insight_text or "").lower()
            if "api rate limit" in lowered_insight or "try again later" in lowered_insight:
                raise HTTPException(
                    status_code=502,
                    detail=f"openclaw_remote_rate_limited: {runtime_agent_id}",
                )
            break
        except HTTPException as exc:
            failure_detail = str(exc.detail)
            should_retry = (
                execution_mode in {"remote_http", "remote", "http"}
                and attempt < remote_retries
                and _is_retryable_remote_error(failure_detail)
            )
            if should_retry:
                attempt += 1
                await asyncio.sleep(min(1.5 * attempt, 4.0))
                continue
            if allow_fallback:
                insight_text = _build_deterministic_fallback_insight(role, evidence)
                break
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

    intake_ctx = await _load_session_intake_context(session_id, db)
    if not intake_ctx.get("ceo_request"):
        intake_ctx["ceo_request"] = str(session_obj.name or "")
    intake_ctx["session_id"] = session_id
    fixed_context = _build_fixed_strategos_context(latest, intake_ctx)
    trace_id = str(uuid.uuid4())
    started = time.perf_counter()

    roles = _board_role_lookup()
    history: List[Dict[str, Any]] = []
    for idx, step_id in enumerate(AGENT_CHAIN_ORDER, start=1):
        role = roles.get(step_id) or step_id.replace("_", " ")
        step_result = await _run_chain_step(
            step_id=step_id,
            role=role,
            step_index=idx,
            ceo_request=str(intake_ctx.get("ceo_request") or ""),
            snapshot=latest,
            fixed_context=fixed_context,
            history=history,
            trace_id=trace_id,
        )
        history.append(step_result)

    total_latency_ms = int((time.perf_counter() - started) * 1000)
    fallback_count = len([h for h in history if h.get("used_fallback")])
    warning_count = len([h for h in history if h.get("warning")])

    synthesis = next((h for h in history if h.get("agent_id") == "synthesis_advisor"), None)
    executive_memo = {}
    if isinstance(synthesis, dict):
        s_out = synthesis.get("structured_output")
        if isinstance(s_out, dict):
            maybe_memo = s_out.get("executive_memo")
            if isinstance(maybe_memo, dict):
                executive_memo = maybe_memo

    await db.execute(
        insert(models.AuditLog).values(
            tenant_id=session_obj.tenant_id,
            actor="advisory_chain",
            action="OPENCLAW_CHAIN_RUN",
            payload=json.dumps(
                {
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "flow_version": FLOW_VERSION,
                    "state": latest.get("state"),
                    "steps": len(history),
                    "fallback_count": fallback_count,
                    "warning_count": warning_count,
                    "total_latency_ms": total_latency_ms,
                }
            ),
        )
    )
    await db.commit()

    return format_response(
        {
            "session_id": session_id,
            "state": latest.get("state"),
            "insights": history,
            "executive_memo": executive_memo,
            "chain_meta": {
                "trace_id": trace_id,
                "flow_version": FLOW_VERSION,
                "steps": len(history),
                "fallback_count": fallback_count,
                "warning_count": warning_count,
                "total_latency_ms": total_latency_ms,
            },
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
