from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select, delete
import uuid
import json

from app.core.response import format_response
from app.db.session import get_session
from app.db import models
from app.services.engine import run_deterministic_engine

router = APIRouter()


class SessionCreate(BaseModel):
    tenant_id: str
    model_version_id: str
    name: str | None = None


@router.post("/sessions")
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_session)):
    try:
        tenant_id = uuid.UUID(payload.tenant_id)
        model_version_id = uuid.UUID(payload.model_version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_uuid_in_payload")

    obj = {
        "tenant_id": tenant_id,
        "model_version_id": model_version_id,
        "name": payload.name,
    }
    stmt = insert(models.TransformationSession).values(**obj).returning(models.TransformationSession.id)
    res = await db.execute(stmt)
    await db.commit()
    inserted = res.scalar()
    if not inserted:
        raise HTTPException(status_code=500, detail="failed_to_create_session")
    return format_response({"session_id": str(inserted)})


@router.get("/sessions")
async def list_sessions(tenant_id: str | None = None, db: AsyncSession = Depends(get_session)):
    """List all sessions, optionally filtered by tenant_id."""
    q = select(models.TransformationSession).order_by(models.TransformationSession.created_at.desc())
    if tenant_id:
        try:
            tid = uuid.UUID(tenant_id)
            q = q.where(models.TransformationSession.tenant_id == tid)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_tenant_id")
    q = q.limit(100)
    res = await db.execute(q)
    rows = res.scalars().all()
    sessions = []
    for s in rows:
        sessions.append({
            "id": str(s.id),
            "tenant_id": str(s.tenant_id),
            "model_version_id": str(s.model_version_id),
            "name": s.name,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "has_snapshot": bool(s.snapshot),
        })
    return format_response({"sessions": sessions})


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str, db: AsyncSession = Depends(get_session)):
    """Get full session detail including snapshot."""
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")
    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    snapshot_data = None
    if session_obj.snapshot:
        try:
            snapshot_data = json.loads(session_obj.snapshot)
        except Exception:
            snapshot_data = {"raw": session_obj.snapshot}
    return format_response({
        "id": str(session_obj.id),
        "tenant_id": str(session_obj.tenant_id),
        "model_version_id": str(session_obj.model_version_id),
        "name": session_obj.name,
        "created_at": session_obj.created_at.isoformat() if session_obj.created_at else None,
        "snapshot": snapshot_data,
    })


@router.get("/sessions/{session_id}/snapshots")
async def get_session_snapshots(session_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    if not session_obj.snapshot:
        return format_response({"session_id": str(sid), "version": 0, "latest": None, "history": []})

    try:
        payload = json.loads(session_obj.snapshot)
    except Exception:
        payload = {
            "version": 0,
            "latest": None,
            "history": [],
            "legacy_snapshot": session_obj.snapshot,
        }

    return format_response({"session_id": str(sid), **payload})


@router.get("/sessions/{session_id}/replay")
async def replay_session(session_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    q = select(models.AuditLog).where(models.AuditLog.action == "ENGINE_RUN")
    res = await db.execute(q)
    rows = res.scalars().all()

    replay_events = []
    for row in rows:
        parsed = None
        if row.payload:
            try:
                parsed = json.loads(row.payload)
            except Exception:
                parsed = {"raw": row.payload}

        if isinstance(parsed, dict) and parsed.get("session_id") == str(sid):
            replay_events.append(
                {
                    "audit_log_id": str(row.id),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "action": row.action,
                    "payload": parsed,
                }
            )

    replay_events.sort(key=lambda x: x.get("created_at") or "")

    return format_response(
        {
            "session_id": str(sid),
            "event_count": len(replay_events),
            "events": replay_events,
        }
    )


@router.get("/sessions/replay/audit/{audit_log_id}")
async def replay_by_audit_id(audit_log_id: str, db: AsyncSession = Depends(get_session)):
    try:
        aid = uuid.UUID(audit_log_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_audit_log_id")

    row = await db.get(models.AuditLog, aid)
    if row is None:
        raise HTTPException(status_code=404, detail="audit_log_not_found")

    if row.action != "ENGINE_RUN":
        raise HTTPException(status_code=400, detail="audit_log_not_engine_run")

    parsed_payload: dict = {}
    if row.payload:
        try:
            parsed_payload = json.loads(row.payload)
        except Exception:
            parsed_payload = {"raw": row.payload}

    model_version_id = parsed_payload.get("model_version_id")
    input_data = parsed_payload.get("input") or {}

    replay_snapshot = None
    replay_error = None
    if model_version_id and isinstance(input_data, dict):
        replay_snapshot = await run_deterministic_engine(
            db,
            model_version_id=model_version_id,
            input_data=input_data,
        )
        if isinstance(replay_snapshot, dict) and replay_snapshot.get("error"):
            replay_error = replay_snapshot.get("error")

    return format_response(
        {
            "audit_log_id": str(row.id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "action": row.action,
            "stored_payload": parsed_payload,
            "replay_snapshot": replay_snapshot,
            "replay_error": replay_error,
        }
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, tenant_id: str | None = None, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_session_id")

    session_obj = await db.get(models.TransformationSession, sid)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    if tenant_id:
        try:
            tid = uuid.UUID(tenant_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_tenant_id")
        if session_obj.tenant_id != tid:
            raise HTTPException(status_code=403, detail="session_tenant_mismatch")

    await db.execute(delete(models.TransformationScenario).where(models.TransformationScenario.session_id == sid))
    await db.execute(delete(models.TransformationSession).where(models.TransformationSession.id == sid))
    await db.commit()

    return format_response({"session_id": str(sid), "deleted": True})
