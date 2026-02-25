from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
import uuid
import json
from datetime import datetime, timezone

from app.core.response import format_response
from app.db.session import get_session
from app.services.engine import run_deterministic_engine
from app.db import models

router = APIRouter()


class EngineRunRequest(BaseModel):
    tenant_id: Optional[str] = None
    model_version_id: Optional[str] = None
    session_id: Optional[str] = None
    input: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Input variables for rule evaluation")


class EngineSnapshot(BaseModel):
    model_version: Dict[str, Any]
    rule_count: int
    triggered_rule_count: int
    conditions_evaluated: int
    state: str
    contributions: list
    scores: Dict[str, float] = Field(default_factory=dict)
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    restructuring_actions: list = Field(default_factory=list)


@router.post(
    "/engine/run",
    response_model=EngineSnapshot,
    responses={
        200: {
            "description": "Engine snapshot",
            "content": {
                "application/json": {
                    "example": {
                        "model_version": {"id": "0000-0000", "name": "Example MV"},
                        "rule_count": 3,
                        "triggered_rule_count": 1,
                        "conditions_evaluated": 4,
                        "state": "NORMAL",
                        "contributions": [{"rule_id": "r1", "condition_id": "c1", "expression": "x < 10", "result": True}],
                        "scores": {"r1": 1.0},
                        "score_breakdown": {
                            "weighted_input_score": 12.5,
                            "rule_impact_score": 1.0,
                            "total_score": 13.5,
                            "coefficient_contributions": [{"name": "revenue", "input": 5, "coefficient": 2.5, "contribution": 12.5}],
                        },
                        "restructuring_actions": [],
                    }
                }
            },
        }
    },
)
async def run_engine(req: EngineRunRequest, db: AsyncSession = Depends(get_session)):
    # Validate basic inputs
    session_obj = None
    session_uuid = None
    if req.session_id:
        try:
            session_uuid = uuid.UUID(str(req.session_id))
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_session_id")
        # ensure session exists
        session_obj = await db.get(models.TransformationSession, session_uuid)
        if session_obj is None:
            raise HTTPException(status_code=404, detail="session_not_found")

    snapshot = await run_deterministic_engine(db, model_version_id=req.model_version_id, input_data=req.input)

    # Always record an audit event for deterministic runs
    tenant_uuid = None
    for candidate in [
        req.tenant_id,
        (snapshot.get("model_version") or {}).get("tenant_id") if isinstance(snapshot, dict) else None,
    ]:
        if not candidate:
            continue
        try:
            tenant_uuid = uuid.UUID(str(candidate))
            break
        except Exception:
            continue

    audit_payload = {
        "model_version_id": req.model_version_id,
        "session_id": req.session_id,
        "input": req.input or {},
        "state": snapshot.get("state") if isinstance(snapshot, dict) else None,
        "total_score": (snapshot.get("score_breakdown") or {}).get("total_score") if isinstance(snapshot, dict) else None,
        "error": snapshot.get("error") if isinstance(snapshot, dict) else None,
    }
    await db.execute(
        insert(models.AuditLog).values(
            tenant_id=tenant_uuid,
            actor="engine_api",
            action="ENGINE_RUN",
            payload=json.dumps(audit_payload),
        )
    )

    # Persist versioned snapshot history if session provided
    if req.session_id and isinstance(snapshot, dict) and not snapshot.get("error"):
        existing_payload: Dict[str, Any] = {}
        if session_obj and session_obj.snapshot:
            try:
                existing_payload = json.loads(session_obj.snapshot)
            except Exception:
                existing_payload = {
                    "version": 0,
                    "latest": None,
                    "history": [],
                    "legacy_snapshot": session_obj.snapshot,
                }

        old_version = int(existing_payload.get("version") or 0)
        new_version = old_version + 1
        old_history = existing_payload.get("history") or []
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

        stmt = (
            models.TransformationSession.__table__
            .update()
            .where(models.TransformationSession.id == session_uuid)
            .values(snapshot=json.dumps(packed))
        )
        await db.execute(stmt)
        await db.commit()
    else:
        await db.commit()

    if snapshot.get("error"):
        raise HTTPException(status_code=400, detail=snapshot)

    return snapshot
