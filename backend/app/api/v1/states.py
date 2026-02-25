from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import format_response
from app.db import models
from app.db.session import get_session

router = APIRouter()


class StateCreate(BaseModel):
    tenant_id: str
    name: str
    description: Optional[str] = None


class StateThresholdCreate(BaseModel):
    tenant_id: str
    threshold: str


@router.post("/states")
async def create_state(payload: StateCreate, db: AsyncSession = Depends(get_session)):
    try:
        tenant_id = uuid.UUID(payload.tenant_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_tenant_id")

    stmt = (
        insert(models.StateDefinition)
        .values(tenant_id=tenant_id, name=payload.name, description=payload.description)
        .returning(models.StateDefinition.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    state_id = res.scalar()
    return format_response({"state_definition_id": str(state_id)})


@router.get("/states")
async def list_states(
    tenant_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_session),
):
    q = select(models.StateDefinition)
    if tenant_id:
        try:
            tid = uuid.UUID(tenant_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_tenant_id")
        q = q.where(models.StateDefinition.tenant_id == tid)

    res = await db.execute(q)
    items = res.scalars().all()
    return format_response(
        {
            "states": [
                {
                    "id": str(s.id),
                    "tenant_id": str(s.tenant_id),
                    "name": s.name,
                    "description": s.description,
                }
                for s in items
            ]
        }
    )


@router.post("/states/{state_definition_id}/thresholds")
async def add_state_threshold(state_definition_id: str, payload: StateThresholdCreate, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(state_definition_id)
        tenant_id = uuid.UUID(payload.tenant_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_uuid_in_payload")

    state = await db.get(models.StateDefinition, sid)
    if state is None:
        raise HTTPException(status_code=404, detail="state_not_found")

    stmt = (
        insert(models.StateThreshold)
        .values(tenant_id=tenant_id, state_definition_id=sid, threshold=payload.threshold)
        .returning(models.StateThreshold.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    threshold_id = res.scalar()
    return format_response({"state_threshold_id": str(threshold_id)})


@router.get("/states/{state_definition_id}/thresholds")
async def list_state_thresholds(state_definition_id: str, db: AsyncSession = Depends(get_session)):
    try:
        sid = uuid.UUID(state_definition_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_state_definition_id")

    q = select(models.StateThreshold).where(models.StateThreshold.state_definition_id == sid)
    res = await db.execute(q)
    items = res.scalars().all()
    return format_response(
        {
            "thresholds": [
                {
                    "id": str(t.id),
                    "state_definition_id": str(t.state_definition_id),
                    "tenant_id": str(t.tenant_id),
                    "threshold": t.threshold,
                }
                for t in items
            ]
        }
    )
