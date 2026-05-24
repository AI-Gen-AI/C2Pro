"""harden documents clauses and chunks rls.

Revision ID: 20260517_0002
Revises: 20260517_0001
Create Date: 2026-05-17

SECURITY HARDENING:
1. Adds direct tenant_id column to documents, clauses, and document_chunks.
2. Backfills tenant_id from projects table.
3. Implements high-performance, fail-closed RLS policies using direct tenant_id.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260517_0002"
down_revision: str | None = "20260517_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add tenant_id columns - Idempotent
    tables = ["documents", "clauses", "document_chunks"]
    for table in tables:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id UUID")

    # 2. Backfill tenant_id from projects
    for table in tables:
        op.execute(
            f"""
            UPDATE {table} t
            SET tenant_id = p.tenant_id
            FROM projects p
            WHERE t.project_id = p.id
              AND t.tenant_id IS NULL
            """
        )

    # 3. Add indices for performance
    for table in tables:
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant ON {table}(tenant_id)")

    # 4. Enable RLS and implement fail-closed policies
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
    tables = ["documents", "clauses", "document_chunks"]
    for table in tables:
        for action in ["select", "insert", "update", "delete"]:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_{action} ON {table}")
        
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_tenant")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id")
