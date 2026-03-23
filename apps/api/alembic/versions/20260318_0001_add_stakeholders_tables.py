"""Add stakeholders and wbs_items tables

Revision ID: 20260318_0001
Revises: 20260317_0001
Create Date: 2026-03-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260318_0001"
down_revision: str = "20260317_clerk_int"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create ENUM types for stakeholders
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'powerlevel') THEN
                CREATE TYPE powerlevel AS ENUM ('low', 'medium', 'high');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'interestlevel') THEN
                CREATE TYPE interestlevel AS ENUM ('low', 'medium', 'high');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stakeholderquadrant') THEN
                CREATE TYPE stakeholderquadrant AS ENUM ('key_player', 'keep_satisfied', 'keep_informed', 'monitor');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'racirole') THEN
                CREATE TYPE racirole AS ENUM ('R', 'A', 'C', 'I');
            END IF;
        END
        $$;
        """
    )

    # Create wbs_items table (needed for stakeholder RACI assignments)
    op.create_table(
        "wbs_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "item_type",
            postgresql.ENUM(
                "deliverable", "work_package", "activity",
                name="wbsitemtype",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("budget_allocated", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("budget_spent", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "wbs_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["wbs_items.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_wbs_items_project", "wbs_items", ["project_id"])
    op.create_index("ix_wbs_items_code", "wbs_items", ["code"])
    op.create_index("ix_wbs_items_parent", "wbs_items", ["parent_id"])

    # Create stakeholders table
    op.create_table(
        "stakeholders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column(
            "power_level",
            postgresql.ENUM(
                "low", "medium", "high",
                name="powerlevel",
                create_type=False,
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "interest_level",
            postgresql.ENUM(
                "low", "medium", "high",
                name="interestlevel",
                create_type=False,
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "quadrant",
            postgresql.ENUM(
                "key_player", "keep_satisfied", "keep_informed", "monitor",
                name="stakeholderquadrant",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("source_clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extracted_from_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "approval_status",
            postgresql.ENUM(
                "PENDING", "APPROVED", "REJECTED", "CORRECTED",
                name="approvalstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column(
            "stakeholder_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_stakeholders_project", "stakeholders", ["project_id"])
    op.create_index("ix_stakeholders_quadrant", "stakeholders", ["quadrant"])
    op.create_index("ix_stakeholders_clause", "stakeholders", ["source_clause_id"])
    op.create_index("ix_stakeholders_email", "stakeholders", ["email"])
    op.create_index("ix_stakeholders_approval", "stakeholders", ["approval_status"])

    # Create stakeholder_wbs_raci table
    op.create_table(
        "stakeholder_wbs_raci",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stakeholder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wbs_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "raci_role",
            postgresql.ENUM(
                "R", "A", "C", "I",
                name="racirole",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("generated_automatically", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("manually_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stakeholder_id"], ["stakeholders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wbs_item_id"], ["wbs_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_raci_project", "stakeholder_wbs_raci", ["project_id"])
    op.create_index("ix_raci_stakeholder", "stakeholder_wbs_raci", ["stakeholder_id"])
    op.create_index("ix_raci_wbs", "stakeholder_wbs_raci", ["wbs_item_id"])
    op.create_index("ix_raci_role", "stakeholder_wbs_raci", ["raci_role"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("stakeholder_wbs_raci")
    op.drop_table("stakeholders")
    op.drop_table("wbs_items")

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS racirole")
    op.execute("DROP TYPE IF EXISTS stakeholderquadrant")
    op.execute("DROP TYPE IF EXISTS interestlevel")
    op.execute("DROP TYPE IF EXISTS powerlevel")
