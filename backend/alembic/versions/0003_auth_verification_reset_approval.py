"""auth verification reset approval

Revision ID: 0003_auth_verification_reset_approval
Revises: 0002_app_users_auth
Create Date: 2026-03-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0003_auth_verification_reset_approval"
down_revision = "0002_app_users_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("app_users", sa.Column("requested_role", sa.String(length=32), nullable=False, server_default="analyst"))
    op.add_column("app_users", sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("app_users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE app_users SET requested_role = role WHERE requested_role IS NULL OR requested_role = ''")
    op.execute("UPDATE app_users SET approval_status = 'approved' WHERE approval_status IS NULL OR approval_status = 'pending'")
    op.execute("UPDATE app_users SET email_verified = true WHERE email_verified IS NULL OR email_verified = false")

    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)
    op.create_index("ix_auth_tokens_user_id_purpose", "auth_tokens", ["user_id", "purpose"], unique=False)


def downgrade():
    op.drop_index("ix_auth_tokens_user_id_purpose", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_column("app_users", "email_verified")
    op.drop_column("app_users", "approval_status")
    op.drop_column("app_users", "requested_role")
