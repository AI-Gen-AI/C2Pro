"""Add analysis, alerts, extractions and procurement tables for LangGraph pipeline

Revision ID: 20260315_0002
Revises: 20260315_0001
Create Date: 2026-03-15 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260315_0002"
down_revision: str = "20260315_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create ENUM types for analysis tables
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'analysistype') THEN
                CREATE TYPE analysistype AS ENUM ('coherence', 'risk', 'cost', 'schedule', 'quality');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'analysisstatus') THEN
                CREATE TYPE analysisstatus AS ENUM ('pending', 'running', 'completed', 'error', 'cancelled');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertseverity') THEN
                CREATE TYPE alertseverity AS ENUM ('critical', 'high', 'medium', 'low');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertstatus') THEN
                CREATE TYPE alertstatus AS ENUM ('open', 'acknowledged', 'resolved', 'dismissed');
            END IF;
        END
        $$;
        """
    )
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

    # Create ENUM types for procurement tables
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'wbsitemtype') THEN
                CREATE TYPE wbsitemtype AS ENUM ('deliverable', 'work_package', 'activity');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bomcategory') THEN
                CREATE TYPE bomcategory AS ENUM ('material', 'equipment', 'service', 'consumable');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'procurementstatus') THEN
                CREATE TYPE procurementstatus AS ENUM ('pending', 'requested', 'ordered', 'in_transit', 'delivered', 'cancelled');
            END IF;
        END
        $$;
        """
    )

    # Create analyses table
    op.create_table(
        "analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "analysis_type",
            postgresql.ENUM(
                "coherence", "risk", "cost", "schedule", "quality",
                name="analysistype",
                create_type=False,
            ),
            nullable=False,
            server_default="coherence",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "running", "completed", "error", "cancelled",
                name="analysisstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("coherence_score", sa.Integer(), nullable=True),
        sa.Column("coherence_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("alerts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "coherence_score >= 0 AND coherence_score <= 100",
            name="ck_analyses_coherence_score"
        ),
    )
    op.create_index("ix_analyses_project", "analyses", ["project_id"])
    op.create_index("ix_analyses_status", "analyses", ["status"])
    op.create_index("ix_analyses_created", "analyses", ["created_at"])

    # Create alerts table
    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "critical", "high", "medium", "low",
                name="alertseverity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("rule_id", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("source_clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_clause_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("affected_entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("impact_level", sa.String(length=20), nullable=True),
        sa.Column("alert_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open", "acknowledged", "resolved", "dismissed",
                name="alertstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="open",
        ),
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
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
    )
    op.create_index("ix_alerts_project", "alerts", ["project_id"])
    op.create_index("ix_alerts_analysis", "alerts", ["analysis_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_clause", "alerts", ["source_clause_id"])
    op.create_index("ix_alerts_created", "alerts", ["created_at"])
    op.create_index("ix_alerts_approval_status", "alerts", ["approval_status"])

    # Create extractions table
    op.create_table(
        "extractions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_type", sa.String(length=50), nullable=True),
        sa.Column("data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extractions_document", "extractions", ["document_id"])
    op.create_index("ix_extractions_type", "extractions", ["extraction_type"])

    # Create procurement_budget_items table (referenced by BOM)
    op.create_table(
        "procurement_budget_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create procurement_wbs_items table
    op.create_table(
        "procurement_wbs_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_code", sa.String(), nullable=True),
        sa.Column(
            "item_type",
            postgresql.ENUM(
                "deliverable", "work_package", "activity",
                name="wbsitemtype",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("budget_allocated", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("budget_spent", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("wbs_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_code"],
            ["procurement_wbs_items.code"],
            name="fk_wbs_parent",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_procurement_wbs_project", "procurement_wbs_items", ["project_id"])

    # Create procurement_bom_items table
    op.create_table(
        "procurement_bom_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("wbs_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("item_code", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            postgresql.ENUM(
                "material", "equipment", "service", "consumable",
                name="bomcategory",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("supplier", sa.String(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("production_time_days", sa.Integer(), nullable=True),
        sa.Column("transit_time_days", sa.Integer(), nullable=True),
        sa.Column("incoterm", sa.String(), nullable=True),
        sa.Column("contract_clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("budget_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "procurement_status",
            postgresql.ENUM(
                "pending", "requested", "ordered", "in_transit", "delivered", "cancelled",
                name="procurementstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("bom_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id"],
            ["procurement_wbs_items.id"],
            name="fk_bom_wbs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["budget_item_id"],
            ["procurement_budget_items.id"],
            name="fk_bom_budget",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_procurement_bom_project", "procurement_bom_items", ["project_id"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("procurement_bom_items")
    op.drop_table("procurement_wbs_items")
    op.drop_table("procurement_budget_items")
    op.drop_table("extractions")
    op.drop_table("alerts")
    op.drop_table("analyses")

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS procurementstatus")
    op.execute("DROP TYPE IF EXISTS bomcategory")
    op.execute("DROP TYPE IF EXISTS wbsitemtype")
    op.execute("DROP TYPE IF EXISTS approvalstatus")
    op.execute("DROP TYPE IF EXISTS alertstatus")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS analysisstatus")
    op.execute("DROP TYPE IF EXISTS analysistype")
