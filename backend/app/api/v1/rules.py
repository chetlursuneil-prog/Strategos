from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import insert, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import format_response
from app.db import models
from app.db.session import get_session

router = APIRouter()


class RuleCreate(BaseModel):
    tenant_id: str
    model_version_id: str
    name: str
    description: Optional[str] = None


class RuleConditionCreate(BaseModel):
    tenant_id: str
    expression: str


class RuleImpactCreate(BaseModel):
    tenant_id: str
    impact: str


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/rules")
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_session)):
    try:
        tenant_id = uuid.UUID(payload.tenant_id)
        model_version_id = uuid.UUID(payload.model_version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_uuid_in_payload")

    stmt = (
        insert(models.Rule)
        .values(
            tenant_id=tenant_id,
            model_version_id=model_version_id,
            name=payload.name,
            description=payload.description,
            is_active=True,
        )
        .returning(models.Rule.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    rule_id = res.scalar()
    return format_response({"rule_id": str(rule_id)})


@router.get("/rules")
async def list_rules(
    tenant_id: Optional[str] = Query(default=None),
    model_version_id: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_session),
):
    q = select(models.Rule)
    if tenant_id:
        try:
            tid = uuid.UUID(tenant_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_tenant_id")
        q = q.where(models.Rule.tenant_id == tid)
    if model_version_id:
        try:
            mv = uuid.UUID(model_version_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_model_version_id")
        q = q.where(models.Rule.model_version_id == mv)
    if active_only:
        q = q.where(models.Rule.is_active == True)

    res = await db.execute(q)
    items = res.scalars().all()
    return format_response(
        {
            "rules": [
                {
                    "id": str(r.id),
                    "tenant_id": str(r.tenant_id),
                    "model_version_id": str(r.model_version_id),
                    "name": r.name,
                    "description": r.description,
                    "is_active": bool(r.is_active),
                }
                for r in items
            ]
        }
    )


@router.patch("/rules/{rule_id}")
async def update_rule(rule_id: str, payload: RuleUpdate, db: AsyncSession = Depends(get_session)):
    try:
        rid = uuid.UUID(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_rule_id")

    rule = await db.get(models.Rule, rid)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule_not_found")

    values = {}
    if payload.name is not None:
        values["name"] = payload.name
    if payload.description is not None:
        values["description"] = payload.description
    if payload.is_active is not None:
        values["is_active"] = payload.is_active

    if not values:
        return format_response({"rule_id": str(rid), "updated": False, "message": "no_fields_provided"})

    await db.execute(update(models.Rule).where(models.Rule.id == rid).values(**values))
    await db.commit()

    refreshed = await db.get(models.Rule, rid)
    return format_response(
        {
            "rule": {
                "id": str(refreshed.id),
                "tenant_id": str(refreshed.tenant_id),
                "model_version_id": str(refreshed.model_version_id),
                "name": refreshed.name,
                "description": refreshed.description,
                "is_active": bool(refreshed.is_active),
            }
        }
    )


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_session)):
    try:
        rid = uuid.UUID(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_rule_id")

    rule = await db.get(models.Rule, rid)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule_not_found")

    await db.execute(delete(models.RuleCondition).where(models.RuleCondition.rule_id == rid))
    await db.execute(delete(models.RuleImpact).where(models.RuleImpact.rule_id == rid))
    await db.execute(delete(models.Rule).where(models.Rule.id == rid))
    await db.commit()

    return format_response({"rule_id": str(rid), "deleted": True})


@router.post("/rules/{rule_id}/conditions")
async def add_rule_condition(rule_id: str, payload: RuleConditionCreate, db: AsyncSession = Depends(get_session)):
    try:
        rid = uuid.UUID(rule_id)
        tenant_id = uuid.UUID(payload.tenant_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_uuid_in_payload")

    rule = await db.get(models.Rule, rid)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule_not_found")

    stmt = (
        insert(models.RuleCondition)
        .values(tenant_id=tenant_id, rule_id=rid, expression=payload.expression, is_active=True)
        .returning(models.RuleCondition.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    condition_id = res.scalar()
    return format_response({"condition_id": str(condition_id)})


@router.post("/rules/{rule_id}/impacts")
async def add_rule_impact(rule_id: str, payload: RuleImpactCreate, db: AsyncSession = Depends(get_session)):
    try:
        rid = uuid.UUID(rule_id)
        tenant_id = uuid.UUID(payload.tenant_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_uuid_in_payload")

    rule = await db.get(models.Rule, rid)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule_not_found")

    stmt = (
        insert(models.RuleImpact)
        .values(tenant_id=tenant_id, rule_id=rid, impact=payload.impact, is_active=True)
        .returning(models.RuleImpact.id)
    )
    res = await db.execute(stmt)
    await db.commit()
    impact_id = res.scalar()
    return format_response({"impact_id": str(impact_id)})


@router.patch("/rules/{rule_id}/deactivate")
async def deactivate_rule(rule_id: str, db: AsyncSession = Depends(get_session)):
    try:
        rid = uuid.UUID(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_rule_id")

    stmt = update(models.Rule).where(models.Rule.id == rid).values(is_active=False)
    res = await db.execute(stmt)
    await db.commit()

    if (res.rowcount or 0) == 0:
        raise HTTPException(status_code=404, detail="rule_not_found")

    return format_response({"rule_id": str(rid), "is_active": False})
