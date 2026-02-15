"""Add approval workflow fields to stakeholders and alerts.

Revision ID: 20260124_0002
Revises: 20260124_0001
Create Date: 2026-01-24
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260124_0002"
down_revision = "20260124_0001"
branch_labels = None
depends_on = None


def _create_enum_if_needed() -> None:
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


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    _create_enum_if_needed()

    approval_enum = sa.Enum(
        "PENDING",
        "APPROVED",
        "REJECTED",
        "CORRECTED",
        name="approvalstatus",
    )

    if _has_table("stakeholders"):
        if not _has_column("stakeholders", "approval_status"):
            op.add_column(
                "stakeholders",
                sa.Column("approval_status", approval_enum, nullable=False, server_default="PENDING"),
            )
        if not _has_column("stakeholders", "reviewed_by"):
            op.add_column("stakeholders", sa.Column("reviewed_by", sa.UUID(), nullable=True))
        if not _has_column("stakeholders", "reviewed_at"):
            op.add_column("stakeholders", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        if not _has_column("stakeholders", "review_comment"):
            op.add_column("stakeholders", sa.Column("review_comment", sa.Text(), nullable=True))

        if _has_column("stakeholders", "approval_status") and not _has_index("stakeholders", "ix_stakeholders_approval_status"):
            op.create_index("ix_stakeholders_approval_status", "stakeholders", ["approval_status"])
        if _has_column("stakeholders", "approval_status"):
            op.alter_column("stakeholders", "approval_status", server_default=None)

    if _has_table("alerts"):
        if not _has_column("alerts", "approval_status"):
            op.add_column(
                "alerts",
                sa.Column("approval_status", approval_enum, nullable=False, server_default="PENDING"),
            )
        if not _has_column("alerts", "reviewed_by"):
            op.add_column("alerts", sa.Column("reviewed_by", sa.UUID(), nullable=True))
        if not _has_column("alerts", "reviewed_at"):
            op.add_column("alerts", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        if not _has_column("alerts", "review_comment"):
            op.add_column("alerts", sa.Column("review_comment", sa.Text(), nullable=True))

        if _has_column("alerts", "approval_status") and not _has_index("alerts", "ix_alerts_approval_status"):
            op.create_index("ix_alerts_approval_status", "alerts", ["approval_status"])
        if _has_column("alerts", "approval_status"):
            op.alter_column("alerts", "approval_status", server_default=None)


def downgrade() -> None:
    if _has_index("alerts", "ix_alerts_approval_status"):
        op.drop_index("ix_alerts_approval_status", table_name="alerts")
    if _has_index("stakeholders", "ix_stakeholders_approval_status"):
        op.drop_index("ix_stakeholders_approval_status", table_name="stakeholders")

    if _has_column("alerts", "review_comment"):
        op.drop_column("alerts", "review_comment")
    if _has_column("alerts", "reviewed_at"):
        op.drop_column("alerts", "reviewed_at")
    if _has_column("alerts", "reviewed_by"):
        op.drop_column("alerts", "reviewed_by")
    if _has_column("alerts", "approval_status"):
        op.drop_column("alerts", "approval_status")

    if _has_column("stakeholders", "review_comment"):
        op.drop_column("stakeholders", "review_comment")
    if _has_column("stakeholders", "reviewed_at"):
        op.drop_column("stakeholders", "reviewed_at")
    if _has_column("stakeholders", "reviewed_by"):
        op.drop_column("stakeholders", "reviewed_by")
    if _has_column("stakeholders", "approval_status"):
        op.drop_column("stakeholders", "approval_status")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS approvalstatus")
