import uuid
from datetime import datetime
import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import (
    build_approval_email,
    build_reset_email,
    build_verification_email,
    send_email,
    smtp_configured,
)
from app.core.response import format_response
from app.core.security import (
    create_access_token,
    decode_access_token,
    expires_in,
    generate_one_time_token,
    hash_one_time_token,
    hash_password,
    utcnow,
    verify_password,
)
from app.db import models
from app.db.session import get_session


router = APIRouter(tags=["auth"])

UserRole = Literal["admin", "analyst", "viewer"]
ApprovalStatus = Literal["pending", "approved", "rejected"]

VERIFY_TTL_SECONDS = int(os.getenv("STRATEGOS_AUTH_VERIFY_TTL_SECONDS", "86400"))  # 24h
RESET_TTL_SECONDS = int(os.getenv("STRATEGOS_AUTH_RESET_TTL_SECONDS", "3600"))  # 1h
PUBLIC_BASE_URL = os.getenv("STRATEGOS_PUBLIC_BASE_URL", "").strip()


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    company_name: Optional[str] = Field(default=None, max_length=255)
    role: UserRole = "analyst"
    tenant_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=12, max_length=512)


class ResendVerifyEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=12, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)


class AdminApproveRequest(BaseModel):
    role: Optional[UserRole] = None


def _normalize_email(raw: str) -> str:
    value = raw.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise HTTPException(status_code=400, detail="invalid_email")
    return value


def _serialize_user(user: models.AppUser) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "requested_role": user.requested_role,
        "approval_status": user.approval_status,
        "email_verified": bool(user.email_verified),
        "tenant_id": str(user.tenant_id),
    }


def _public_base_url(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    if host:
        return f"{proto}://{host}".rstrip("/")
    return "http://localhost:3000"


async def _resolve_tenant_id(
    db: AsyncSession,
    provided_tenant_id: Optional[str],
    company_name: Optional[str],
) -> uuid.UUID:
    if provided_tenant_id:
        try:
            tenant_uuid = uuid.UUID(provided_tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_tenant_id") from exc
        tenant = await db.get(models.Tenant, tenant_uuid)
        if not tenant:
            raise HTTPException(status_code=400, detail="tenant_not_found")
        return tenant_uuid

    mv_res = await db.execute(
        select(models.ModelVersion.tenant_id).order_by(models.ModelVersion.created_at.asc()).limit(1)
    )
    mv_tenant_id = mv_res.scalar()
    if mv_tenant_id:
        return mv_tenant_id

    tenant_res = await db.execute(select(models.Tenant.id).order_by(models.Tenant.created_at.asc()).limit(1))
    existing_tenant_id = tenant_res.scalar()
    if existing_tenant_id:
        return existing_tenant_id

    new_tenant_id = uuid.uuid4()
    await db.execute(
        insert(models.Tenant).values(
            id=new_tenant_id,
            name=(company_name.strip() if company_name else "Default Tenant"),
        )
    )
    await db.commit()
    return new_tenant_id


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authorization")
    prefix = "bearer "
    if not authorization.lower().startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid_authorization_scheme")
    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return token


async def _get_current_user(
    db: AsyncSession,
    authorization: Optional[str],
) -> models.AppUser:
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    raw_user_id = payload.get("sub")
    try:
        user_id = uuid.UUID(str(raw_user_id))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid_token_subject") from exc

    user = await db.get(models.AppUser, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user_not_found_or_inactive")
    return user


async def _create_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    purpose: str,
    ttl_seconds: int,
) -> tuple[str, datetime]:
    raw = generate_one_time_token()
    token_hash = hash_one_time_token(raw)
    expires_at = expires_in(ttl_seconds)
    await db.execute(
        insert(models.AuthToken).values(
            id=uuid.uuid4(),
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
        )
    )
    return raw, expires_at


async def _consume_token(
    db: AsyncSession,
    raw_token: str,
    purpose: str,
) -> models.AuthToken:
    token_hash = hash_one_time_token(raw_token)
    res = await db.execute(
        select(models.AuthToken).where(
            models.AuthToken.token_hash == token_hash,
            models.AuthToken.purpose == purpose,
        )
    )
    token_obj = res.scalars().first()
    if not token_obj:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    if token_obj.used_at is not None:
        raise HTTPException(status_code=400, detail="token_already_used")
    now = utcnow()
    expires_at = token_obj.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=now.tzinfo)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    token_obj.used_at = now
    return token_obj


def _send_verification(
    user: models.AppUser,
    request: Request,
    raw_token: str,
) -> dict:
    verify_url = f"{_public_base_url(request)}/verify-email?token={raw_token}"
    subject, body = build_verification_email(user.name, verify_url)
    sent = send_email(subject, user.email, body)
    payload = {"email_delivery": "sent" if sent else "not_configured_or_failed"}
    if not sent and not smtp_configured():
        payload["verification_url"] = verify_url
    return payload


def _send_reset(
    user: models.AppUser,
    request: Request,
    raw_token: str,
) -> dict:
    reset_url = f"{_public_base_url(request)}/reset-password?token={raw_token}"
    subject, body = build_reset_email(user.name, reset_url)
    sent = send_email(subject, user.email, body)
    payload = {"email_delivery": "sent" if sent else "not_configured_or_failed"}
    if not sent and not smtp_configured():
        payload["reset_url"] = reset_url
    return payload


@router.post("/auth/register")
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_session)):
    email = _normalize_email(payload.email)
    existing = await db.execute(select(models.AppUser.id).where(models.AppUser.email == email))
    if existing.scalar():
        raise HTTPException(status_code=409, detail="email_already_registered")

    tenant_id = await _resolve_tenant_id(db, payload.tenant_id, payload.company_name)
    users_count_res = await db.execute(
        select(func.count(models.AppUser.id)).where(models.AppUser.tenant_id == tenant_id)
    )
    users_count = int(users_count_res.scalar() or 0)

    requested_role: UserRole = payload.role
    if users_count == 0:
        approval_status: ApprovalStatus = "approved"
        effective_role: UserRole = "admin"
    else:
        approval_status = "pending"
        effective_role = "viewer"

    user_id = uuid.uuid4()
    await db.execute(
        insert(models.AppUser).values(
            id=user_id,
            tenant_id=tenant_id,
            email=email,
            name=payload.name.strip(),
            role=effective_role,
            requested_role=requested_role,
            approval_status=approval_status,
            email_verified=False,
            password_hash=hash_password(payload.password),
            is_active=True,
        )
    )
    verify_token, _ = await _create_token(db, user_id, "verify_email", VERIFY_TTL_SECONDS)
    await db.commit()

    user_res = await db.execute(select(models.AppUser).where(models.AppUser.id == user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=500, detail="user_creation_failed")

    delivery_info = _send_verification(user, request, verify_token)
    return format_response(
        {
            "user": _serialize_user(user),
            "verification_required": True,
            "approval_required": user.approval_status != "approved",
            **delivery_info,
        }
    )


@router.post("/auth/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_session)):
    email = _normalize_email(payload.email)
    res = await db.execute(select(models.AppUser).where(models.AppUser.email == email))
    user = res.scalars().first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="email_not_verified")
    if user.approval_status == "pending":
        raise HTTPException(status_code=403, detail="account_pending_approval")
    if user.approval_status == "rejected":
        raise HTTPException(status_code=403, detail="account_rejected")

    token = create_access_token(str(user.id), user.email)
    return format_response({"token": token, "user": _serialize_user(user)})


@router.post("/auth/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_session)):
    token_obj = await _consume_token(db, payload.token.strip(), "verify_email")
    user = await db.get(models.AppUser, token_obj.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    user.email_verified = True
    await db.commit()

    can_login = user.is_active and user.approval_status == "approved"
    out = {"user": _serialize_user(user), "can_login": can_login}
    if can_login:
        out["token"] = create_access_token(str(user.id), user.email)
    return format_response(out)


@router.post("/auth/verify-email/resend")
async def resend_verify_email(payload: ResendVerifyEmailRequest, request: Request, db: AsyncSession = Depends(get_session)):
    email = _normalize_email(payload.email)
    res = await db.execute(select(models.AppUser).where(models.AppUser.email == email))
    user = res.scalars().first()
    if not user:
        return format_response({"message": "If the account exists, a verification email has been sent."})
    if user.email_verified:
        return format_response({"message": "email_already_verified"})

    raw, _ = await _create_token(db, user.id, "verify_email", VERIFY_TTL_SECONDS)
    await db.commit()
    delivery = _send_verification(user, request, raw)
    return format_response({"message": "verification_email_sent", **delivery})


@router.post("/auth/password/forgot")
async def forgot_password(payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_session)):
    email = _normalize_email(payload.email)
    res = await db.execute(select(models.AppUser).where(models.AppUser.email == email))
    user = res.scalars().first()
    if not user or not user.is_active:
        return format_response({"message": "If the account exists, a password reset link has been sent."})
    if not user.email_verified:
        return format_response({"message": "email_not_verified"})

    raw, _ = await _create_token(db, user.id, "reset_password", RESET_TTL_SECONDS)
    await db.commit()
    delivery = _send_reset(user, request, raw)
    return format_response({"message": "password_reset_email_sent", **delivery})


@router.post("/auth/password/reset")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_session)):
    token_obj = await _consume_token(db, payload.token.strip(), "reset_password")
    user = await db.get(models.AppUser, token_obj.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="user_not_found")
    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(models.AuthToken)
        .where(
            models.AuthToken.user_id == user.id,
            models.AuthToken.purpose == "reset_password",
            models.AuthToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    await db.commit()
    return format_response({"message": "password_reset_successful"})


@router.get("/auth/me")
async def me(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(db, authorization)
    return format_response({"user": _serialize_user(user)})


@router.get("/auth/admin/pending-users")
async def list_pending_users(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_session),
):
    actor = await _get_current_user(db, authorization)
    if actor.role != "admin" or actor.approval_status != "approved":
        raise HTTPException(status_code=403, detail="admin_required")

    res = await db.execute(
        select(models.AppUser).where(
            models.AppUser.tenant_id == actor.tenant_id,
            models.AppUser.approval_status == "pending",
            models.AppUser.id != actor.id,
        )
    )
    users = res.scalars().all()
    return format_response({"pending_users": [_serialize_user(u) for u in users]})


@router.post("/auth/admin/users/{user_id}/approve")
async def approve_user(
    user_id: str,
    payload: AdminApproveRequest,
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_session),
):
    actor = await _get_current_user(db, authorization)
    if actor.role != "admin" or actor.approval_status != "approved":
        raise HTTPException(status_code=403, detail="admin_required")

    try:
        target_id = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_user_id") from exc

    target = await db.get(models.AppUser, target_id)
    if not target or target.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="user_not_found")
    if target.approval_status == "approved":
        return format_response({"user": _serialize_user(target), "message": "already_approved"})

    target.approval_status = "approved"
    target.role = payload.role or target.requested_role or "analyst"
    await db.commit()

    subject, body = build_approval_email(target.name, approved=True, role=target.role)
    send_email(subject, target.email, body)

    return format_response({"user": _serialize_user(target), "message": "user_approved"})


@router.post("/auth/admin/users/{user_id}/reject")
async def reject_user(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_session),
):
    actor = await _get_current_user(db, authorization)
    if actor.role != "admin" or actor.approval_status != "approved":
        raise HTTPException(status_code=403, detail="admin_required")

    try:
        target_id = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_user_id") from exc

    target = await db.get(models.AppUser, target_id)
    if not target or target.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="user_not_found")

    target.approval_status = "rejected"
    target.is_active = False
    await db.commit()

    subject, body = build_approval_email(target.name, approved=False, role=None)
    send_email(subject, target.email, body)

    return format_response({"user": _serialize_user(target), "message": "user_rejected"})
