"""Add disclaimer_acceptances table for gate-8 legal disclaimer persistence.

Revision ID: 20260807_0001
Revises: 20260805_0001
Create Date: 2026-08-07

SEC-014: Replace in-process app.state disclaimer tracking with a DB-backed
table so acceptances survive pod restarts and multi-replica deployments.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260807_0001"
down_revision: str | None = "20260805_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "disclaimer_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "project_id", "version",
            name="uq_disclaimer_acceptance",
        ),
    )
    op.create_index("ix_disclaimer_acceptances_tenant_id", "disclaimer_acceptances", ["tenant_id"])

    op.execute("ALTER TABLE disclaimer_acceptances ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE disclaimer_acceptances FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY disclaimer_tenant_isolation_select ON disclaimer_acceptances
            FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY disclaimer_tenant_isolation_insert ON disclaimer_acceptances
            FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS disclaimer_tenant_isolation_insert ON disclaimer_acceptances")
    op.execute("DROP POLICY IF EXISTS disclaimer_tenant_isolation_select ON disclaimer_acceptances")
    op.drop_index("ix_disclaimer_acceptances_tenant_id", table_name="disclaimer_acceptances")
    op.drop_table("disclaimer_acceptances")
