import os
import smtplib
from email.message import EmailMessage
from typing import Optional


SMTP_HOST = os.getenv("STRATEGOS_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("STRATEGOS_SMTP_PORT", "587"))
SMTP_USER = os.getenv("STRATEGOS_SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("STRATEGOS_SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("STRATEGOS_SMTP_FROM", "").strip() or SMTP_USER
SMTP_USE_TLS = os.getenv("STRATEGOS_SMTP_USE_TLS", "true").strip().lower() != "false"


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def send_email(subject: str, to_email: str, body_text: str) -> bool:
    if not smtp_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False


def build_verification_email(name: str, verify_url: str) -> tuple[str, str]:
    subject = "Verify your STRATEGOS account"
    body = (
        f"Hi {name},\n\n"
        "Please verify your STRATEGOS account by opening this link:\n"
        f"{verify_url}\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )
    return subject, body


def build_reset_email(name: str, reset_url: str) -> tuple[str, str]:
    subject = "Reset your STRATEGOS password"
    body = (
        f"Hi {name},\n\n"
        "You requested a password reset. Open this link to set a new password:\n"
        f"{reset_url}\n\n"
        "If you did not request this, ignore this email.\n"
    )
    return subject, body


def build_approval_email(name: str, approved: bool, role: Optional[str]) -> tuple[str, str]:
    if approved:
        subject = "Your STRATEGOS access is approved"
        body = (
            f"Hi {name},\n\n"
            f"Your STRATEGOS access request has been approved"
            f"{f' with role {role}' if role else ''}.\n"
            "You can now log in.\n"
        )
    else:
        subject = "Your STRATEGOS access request was rejected"
        body = (
            f"Hi {name},\n\n"
            "Your STRATEGOS access request was rejected by an administrator.\n"
            "Please contact your workspace admin for details.\n"
        )
    return subject, body
