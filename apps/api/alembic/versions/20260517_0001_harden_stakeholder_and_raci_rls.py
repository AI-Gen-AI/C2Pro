"""harden stakeholder and raci rls.

Revision ID: 20260517_0001
Revises: 20260516_0001
Create Date: 2026-05-17

SECURITY HARDENING:
1. Adds direct tenant_id column to stakeholders and stakeholder_wbs_raci.
2. Backfills tenant_id from projects table.
3. Implements high-performance, fail-closed RLS policies using direct tenant_id.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260517_0001"
down_revision: str | None = "20260516_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add tenant_id columns - Idempotent
    op.execute("ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS tenant_id UUID")
    op.execute("ALTER TABLE stakeholder_wbs_raci ADD COLUMN IF NOT EXISTS tenant_id UUID")

    # 2. Backfill tenant_id from projects
    op.execute(
        """
        UPDATE stakeholders s
        SET tenant_id = p.tenant_id
        FROM projects p
        WHERE s.project_id = p.id
          AND s.tenant_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE stakeholder_wbs_raci r
        SET tenant_id = p.tenant_id
        FROM projects p
        WHERE r.project_id = p.id
          AND r.tenant_id IS NULL
        """
    )

    # 3. Add indices for performance
    op.execute("CREATE INDEX IF NOT EXISTS ix_stakeholders_tenant ON stakeholders(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_raci_tenant ON stakeholder_wbs_raci(tenant_id)")

    # 4. Enable RLS and implement fail-closed policies
    tables = ["stakeholders", "stakeholder_wbs_raci"]
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # Drop legacy join-based policies
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")

        # Drop possible crud-specific legacy policies
        for action in ["select", "insert", "update", "delete"]:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_{action} ON {table}")

        # Create new optimized fail-closed policies
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation_select ON {table}
                FOR SELECT
                USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation_insert ON {table}
                FOR INSERT
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation_update ON {table}
                FOR UPDATE
                USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation_delete ON {table}
                FOR DELETE
                USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )


def downgrade() -> None:
    # Reverting to legacy join-based policies would be complex and risky.
    # Usually, hardening migrations are one-way in production.
    # But for development parity, we drop the new policies and disable RLS.
    tables = ["stakeholders", "stakeholder_wbs_raci"]
    for table in tables:
        for action in ["select", "insert", "update", "delete"]:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_{action} ON {table}")

        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_raci_tenant", "stakeholder_wbs_raci")
    op.drop_index("ix_stakeholders_tenant", "stakeholders")

    op.drop_column("stakeholder_wbs_raci", "tenant_id")
    op.drop_column("stakeholders", "tenant_id")
