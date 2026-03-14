import uuid
import asyncio

from sqlalchemy import insert

from fastapi.testclient import TestClient

from app.main import app
from app.db import models as m
from app.db.session import AsyncSessionLocal


client = TestClient(app)


def _random_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def _create_tenant(name: str) -> str:
    tenant_id = uuid.uuid4()

    async def _run():
        async with AsyncSessionLocal() as db:
            await db.execute(insert(m.Tenant).values(id=tenant_id, name=name))
            await db.commit()

    asyncio.run(_run())
    return str(tenant_id)


def test_register_login_me_flow():
    tenant_id = _create_tenant("tenant-auth-basic")
    email = _random_email()
    password = "StrongPass123"

    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test User",
            "email": email,
            "password": password,
            "tenant_id": tenant_id,
            "company_name": "Acme Corp",
            "role": "admin",
        },
    )
    assert register_resp.status_code == 200
    register_body = register_resp.json()
    assert register_body["status"] == "success"
    assert register_body["data"]["user"]["email"] == email
    assert register_body["data"]["verification_required"] is True
    assert register_body["data"]["verification_url"]

    pre_verify_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert pre_verify_login.status_code == 403
    assert pre_verify_login.json()["detail"] == "email_not_verified"

    verify_resp = client.post(
        "/api/v1/auth/verify-email",
        json={"token": register_body["data"]["verification_url"].split("token=")[-1]},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["data"]["user"]["email_verified"] is True

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["token"]
    assert token

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_body = me_resp.json()
    assert me_body["data"]["user"]["email"] == email


def test_register_duplicate_email_rejected():
    email = _random_email()
    payload = {"name": "User A", "email": email, "password": "StrongPass123"}

    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 200

    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_login_invalid_credentials():
    email = _random_email()
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"name": "User B", "email": email, "password": "StrongPass123"},
    )
    assert register_resp.status_code == 200

    verify_resp = client.post(
        "/api/v1/auth/verify-email",
        json={"token": register_resp.json()["data"]["verification_url"].split("token=")[-1]},
    )
    assert verify_resp.status_code == 200

    bad_login = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPass999"})
    assert bad_login.status_code == 401


def test_pending_approval_then_admin_approve():
    tenant_id = _create_tenant("tenant-auth-approval")

    admin_email = _random_email()
    admin_password = "StrongPass123"
    admin_reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Tenant Admin",
            "email": admin_email,
            "password": admin_password,
            "tenant_id": tenant_id,
            "role": "admin",
        },
    )
    assert admin_reg.status_code == 200
    admin_verify = client.post(
        "/api/v1/auth/verify-email",
        json={"token": admin_reg.json()["data"]["verification_url"].split("token=")[-1]},
    )
    assert admin_verify.status_code == 200
    admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": admin_password})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["data"]["token"]

    member_email = _random_email()
    member_password = "StrongPass123"
    member_reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Member",
            "email": member_email,
            "password": member_password,
            "tenant_id": tenant_id,
            "role": "analyst",
        },
    )
    assert member_reg.status_code == 200
    assert member_reg.json()["data"]["approval_required"] is True

    member_verify = client.post(
        "/api/v1/auth/verify-email",
        json={"token": member_reg.json()["data"]["verification_url"].split("token=")[-1]},
    )
    assert member_verify.status_code == 200

    member_login_pending = client.post("/api/v1/auth/login", json={"email": member_email, "password": member_password})
    assert member_login_pending.status_code == 403
    assert member_login_pending.json()["detail"] == "account_pending_approval"

    pending = client.get("/api/v1/auth/admin/pending-users", headers={"Authorization": f"Bearer {admin_token}"})
    assert pending.status_code == 200
    users = pending.json()["data"]["pending_users"]
    target = next((u for u in users if u["email"] == member_email), None)
    assert target

    approve = client.post(
        f"/api/v1/auth/admin/users/{target['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "analyst"},
    )
    assert approve.status_code == 200
    assert approve.json()["data"]["user"]["approval_status"] == "approved"

    member_login_ok = client.post("/api/v1/auth/login", json={"email": member_email, "password": member_password})
    assert member_login_ok.status_code == 200


def test_forgot_reset_password_flow():
    email = _random_email()
    password = "StrongPass123"
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": "Reset User", "email": email, "password": password},
    )
    assert reg.status_code == 200

    verify = client.post(
        "/api/v1/auth/verify-email",
        json={"token": reg.json()["data"]["verification_url"].split("token=")[-1]},
    )
    assert verify.status_code == 200

    forgot = client.post("/api/v1/auth/password/forgot", json={"email": email})
    assert forgot.status_code == 200
    reset_url = forgot.json()["data"].get("reset_url")
    assert reset_url
    token = reset_url.split("token=")[-1]

    reset = client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "NewStrongPass123"})
    assert reset.status_code == 200

    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert old_login.status_code == 401

    new_login = client.post("/api/v1/auth/login", json={"email": email, "password": "NewStrongPass123"})
    assert new_login.status_code == 200
