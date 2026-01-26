"""Add approval workflow fields to stakeholders and alerts.

Revision ID: 20260124_0002
Revises: 20260124_0001
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260124_0002"
down_revision = "20260124_0001"
branch_labels = None
depends_on = None


def _create_enum_if_needed():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'approvalstatus') THEN
                CREATE TYPE approvalstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CORRECTED');
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _create_enum_if_needed()

    approval_enum = sa.Enum(
        "PENDING",
        "APPROVED",
        "REJECTED",
        "CORRECTED",
        name="approvalstatus",
    )

    op.add_column(
        "stakeholders",
        sa.Column("approval_status", approval_enum, nullable=False, server_default="PENDING"),
    )
    op.add_column("stakeholders", sa.Column("reviewed_by", sa.UUID(), nullable=True))
    op.add_column("stakeholders", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("stakeholders", sa.Column("review_comment", sa.Text(), nullable=True))

    op.add_column(
        "alerts",
        sa.Column("approval_status", approval_enum, nullable=False, server_default="PENDING"),
    )
    op.add_column("alerts", sa.Column("reviewed_by", sa.UUID(), nullable=True))
    op.add_column("alerts", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("alerts", sa.Column("review_comment", sa.Text(), nullable=True))

    op.create_index("ix_stakeholders_approval_status", "stakeholders", ["approval_status"])
    op.create_index("ix_alerts_approval_status", "alerts", ["approval_status"])

    op.alter_column("stakeholders", "approval_status", server_default=None)
    op.alter_column("alerts", "approval_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_alerts_approval_status", table_name="alerts")
    op.drop_index("ix_stakeholders_approval_status", table_name="stakeholders")

    op.drop_column("alerts", "review_comment")
    op.drop_column("alerts", "reviewed_at")
    op.drop_column("alerts", "reviewed_by")
    op.drop_column("alerts", "approval_status")

    op.drop_column("stakeholders", "review_comment")
    op.drop_column("stakeholders", "reviewed_at")
    op.drop_column("stakeholders", "reviewed_by")
    op.drop_column("stakeholders", "approval_status")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS approvalstatus")
