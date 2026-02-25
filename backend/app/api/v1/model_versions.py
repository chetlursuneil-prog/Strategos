from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import format_response
from app.db import models
from app.db.session import get_session

router = APIRouter()


class ModelVersionCreate(BaseModel):
    tenant_id: str
    name: str
    description: Optional[str] = None
    is_active: bool = True


@router.post("/models/versions")
async def create_model_version(payload: ModelVersionCreate, db: AsyncSession = Depends(get_session)):
    try:
        tenant_id = uuid.UUID(payload.tenant_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_tenant_id")

    stmt = (
        insert(models.ModelVersion)
        .values(
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
        )
        .returning(models.ModelVersion.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    mv_id = res.scalar()
    return format_response({"model_version_id": str(mv_id)})


@router.get("/models/versions")
async def list_model_versions(
    tenant_id: Optional[str] = Query(default=None),
    active_only: bool = Query(default=False),
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
    items = res.scalars().all()
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
                for mv in items
            ]
        }
    )


@router.patch("/models/versions/{model_version_id}/activate")
async def activate_model_version(model_version_id: str, db: AsyncSession = Depends(get_session)):
    try:
        mv_id = uuid.UUID(model_version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_model_version_id")

    existing = await db.get(models.ModelVersion, mv_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="model_version_not_found")

    # keep a single active version per tenant
    await db.execute(
        update(models.ModelVersion)
        .where(models.ModelVersion.tenant_id == existing.tenant_id)
        .values(is_active=False)
    )
    await db.execute(update(models.ModelVersion).where(models.ModelVersion.id == mv_id).values(is_active=True))
    await db.commit()
    return format_response({"model_version_id": str(mv_id), "is_active": True})
