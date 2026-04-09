"""add notification_configs table

Revision ID: 20260406_0003
Revises: 20260406_0002
Create Date: 2026-04-06

TASK-BCK-025: Add real notification delivery beyond log-only.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260406_0003"
down_revision: str | None = "20260406_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create notification_configs table for per-tenant notification configuration."""
    op.create_table(
        "notification_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "notification_channels",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("email_recipients", postgresql.JSONB, nullable=True),
        sa.Column("slack_webhook_url", sa.Text, nullable=True),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("webhook_auth_token", sa.Text, nullable=True),
        sa.Column("custom_headers", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Enable RLS (Row Level Security) for tenant isolation
    op.execute("ALTER TABLE notification_configs ENABLE ROW LEVEL SECURITY")

    # Create RLS policy for tenant isolation
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notification_configs
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    """Drop notification_configs table."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notification_configs")
    op.drop_table("notification_configs")
