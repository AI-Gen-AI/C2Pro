"""Create review_items table for HITL review queue.

Revision ID: 20260225_0001
Revises: 20260205_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

revision: str = "20260225_0001"
down_revision: str | None = "20260205_0001"
branch_labels = None
depends_on = None


review_status_enum = ENUM(
    "DRAFT",
    "PENDING_REVIEW_REQUIRED",
    "PENDING_REVIEW_CONDITIONAL",
    "APPROVED",
    "REJECTED",
    "ESCALATED",
    "CLOSED",
    name="reviewstatus",
    create_type=False,
)

impact_level_enum = ENUM(
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    name="impactlevel",
    create_type=False,
)


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def _policy_exists(table_name: str, policy_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = current_schema()
              AND tablename = :table_name
              AND policyname = :policy_name
            """
        ),
        {"table_name": table_name, "policy_name": policy_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reviewstatus') THEN
                CREATE TYPE reviewstatus AS ENUM (
                    'DRAFT',
                    'PENDING_REVIEW_REQUIRED',
                    'PENDING_REVIEW_CONDITIONAL',
                    'APPROVED',
                    'REJECTED',
                    'ESCALATED',
                    'CLOSED'
                );
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'impactlevel') THEN
                CREATE TYPE impactlevel AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
            END IF;
        END
        $$;
    """)

    if not _has_table("review_items"):
        op.create_table(
            "review_items",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("item_id", UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("item_type", sa.String(128), nullable=False),
            sa.Column(
                "current_status",
                review_status_enum,
                nullable=False,
                server_default="DRAFT",
            ),
            sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
            sa.Column(
                "impact_level",
                impact_level_enum,
                nullable=False,
                server_default="LOW",
            ),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("approved_by", sa.String(256), nullable=True),
            sa.Column("approved_at", sa.DateTime, nullable=True),
            sa.Column("sla_due_date", sa.DateTime, nullable=False),
            sa.Column("item_data", JSONB, nullable=False, server_default="{}"),
            sa.Column("review_metadata", JSONB, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    if not _has_index("review_items", "ix_review_items_tenant_status"):
        op.create_index("ix_review_items_tenant_status", "review_items", ["tenant_id", "current_status"])
    if not _has_index("review_items", "ix_review_items_sla_due"):
        op.create_index("ix_review_items_sla_due", "review_items", ["sla_due_date"])

    # Enable RLS
    op.execute("ALTER TABLE review_items ENABLE ROW LEVEL SECURITY")
    if not _policy_exists("review_items", "tenant_isolation_select"):
        op.execute("""
            CREATE POLICY tenant_isolation_select ON review_items
            FOR SELECT
            USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
        """)
    if not _policy_exists("review_items", "tenant_isolation_insert"):
        op.execute("""
            CREATE POLICY tenant_isolation_insert ON review_items
            FOR INSERT
            WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
        """)
    if not _policy_exists("review_items", "tenant_isolation_update"):
        op.execute("""
            CREATE POLICY tenant_isolation_update ON review_items
            FOR UPDATE
            USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
        """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON review_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON review_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON review_items")
    op.execute("ALTER TABLE review_items DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_review_items_sla_due", table_name="review_items")
    op.drop_index("ix_review_items_tenant_status", table_name="review_items")
    op.drop_table("review_items")

    op.execute("DROP TYPE IF EXISTS impactlevel")
    op.execute("DROP TYPE IF EXISTS reviewstatus")
