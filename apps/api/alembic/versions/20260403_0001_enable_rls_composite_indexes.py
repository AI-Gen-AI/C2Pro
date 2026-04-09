"""Enable RLS and add composite indexes for documents/clauses

Revision ID: 20260403_0001
Revises: 20260401_0001
Create Date: 2026-04-03 00:00:00.000000

Supabase Postgres Best Practices:
- security-003: Enable RLS on documents and clauses tables
- query-001: Add composite indexes for tenant-scoped queries
- monitor-001: Enable pg_stat_statements extension

Suite ID: TS-DB-MIG-RLS-001

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260403_0001"
down_revision: str = "20260401_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ===========================================
    # ENABLE PG_STAT_STATEMENTS EXTENSION
    # ===========================================
    # monitor-001: Enable query performance monitoring
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

    # ===========================================
    # ENABLE ROW LEVEL SECURITY ON DOCUMENTS
    # ===========================================
    # security-003: Enable RLS on documents table
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")

    # Documents: SELECT - tenant isolation via project -> tenant
    op.execute("""
        CREATE POLICY documents_tenant_isolation_select ON documents
        FOR SELECT
        USING (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # Documents: INSERT - enforce tenant via project
    op.execute("""
        CREATE POLICY documents_tenant_isolation_insert ON documents
        FOR INSERT
        WITH CHECK (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # Documents: UPDATE - tenant isolation
    op.execute("""
        CREATE POLICY documents_tenant_isolation_update ON documents
        FOR UPDATE
        USING (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # Documents: DELETE - tenant isolation
    op.execute("""
        CREATE POLICY documents_tenant_isolation_delete ON documents
        FOR DELETE
        USING (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # ===========================================
    # ENABLE ROW LEVEL SECURITY ON CLAUSES
    # ===========================================
    # security-003: Enable RLS on clauses table
    op.execute("ALTER TABLE clauses ENABLE ROW LEVEL SECURITY")

    # Clauses: SELECT - tenant isolation via document -> project -> tenant
    op.execute("""
        CREATE POLICY clauses_tenant_isolation_select ON clauses
        FOR SELECT
        USING (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # Clauses: INSERT - enforce tenant via document -> project
    op.execute("""
        CREATE POLICY clauses_tenant_isolation_insert ON clauses
        FOR INSERT
        WITH CHECK (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # Clauses: UPDATE - tenant isolation
    op.execute("""
        CREATE POLICY clauses_tenant_isolation_update ON clauses
        FOR UPDATE
        USING (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # Clauses: DELETE - tenant isolation
    op.execute("""
        CREATE POLICY clauses_tenant_isolation_delete ON clauses
        FOR DELETE
        USING (
            project_id IN (
                SELECT id FROM projects
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    (SELECT tenant_id FROM projects WHERE id = project_id)
                )
            )
        )
    """)

    # ===========================================
    # ADD COMPOSITE INDEXES FOR QUERY PERFORMANCE
    # ===========================================
    # query-001: Composite indexes for tenant-scoped queries

    # Documents: tenant + status for filtering
    op.create_index(
        "ix_documents_tenant_status",
        "documents",
        ["project_id", "upload_status"],
        postgresql_using="btree"
    )

    # Documents: tenant + type for filtering
    op.create_index(
        "ix_documents_tenant_type",
        "documents",
        ["project_id", "document_type"],
        postgresql_using="btree"
    )

    # Documents: tenant + created_at for sorting
    op.create_index(
        "ix_documents_tenant_created",
        "documents",
        ["project_id", "created_at"],
        postgresql_using="btree"
    )

    # Clauses: tenant + project + type for filtering
    op.create_index(
        "ix_clauses_tenant_project_type",
        "clauses",
        ["project_id", "clause_type"],
        postgresql_using="btree"
    )

    # Clauses: tenant + project + code for lookups
    op.create_index(
        "ix_clauses_tenant_project_code",
        "clauses",
        ["project_id", "clause_code"],
        postgresql_using="btree"
    )

    # Clauses: tenant + project + verification status
    op.create_index(
        "ix_clauses_tenant_verified",
        "clauses",
        ["project_id", "manually_verified", "verified_at"],
        postgresql_using="btree"
    )


def downgrade() -> None:
    # ===========================================
    # DROP COMPOSITE INDEXES
    # ===========================================

    op.drop_index("ix_clauses_tenant_verified", "clauses")
    op.drop_index("ix_clauses_tenant_project_code", "clauses")
    op.drop_index("ix_clauses_tenant_project_type", "clauses")
    op.drop_index("ix_documents_tenant_created", "documents")
    op.drop_index("ix_documents_tenant_type", "documents")
    op.drop_index("ix_documents_tenant_status", "documents")

    # ===========================================
    # DROP RLS POLICIES FROM CLAUSES
    # ===========================================

    op.execute("DROP POLICY IF EXISTS clauses_tenant_isolation_delete ON clauses")
    op.execute("DROP POLICY IF EXISTS clauses_tenant_isolation_update ON clauses")
    op.execute("DROP POLICY IF EXISTS clauses_tenant_isolation_insert ON clauses")
    op.execute("DROP POLICY IF EXISTS clauses_tenant_isolation_select ON clauses")
    op.execute("ALTER TABLE clauses DISABLE ROW LEVEL SECURITY")

    # ===========================================
    # DROP RLS POLICIES FROM DOCUMENTS
    # ===========================================

    op.execute("DROP POLICY IF EXISTS documents_tenant_isolation_delete ON documents")
    op.execute("DROP POLICY IF EXISTS documents_tenant_isolation_update ON documents")
    op.execute("DROP POLICY IF EXISTS documents_tenant_isolation_insert ON documents")
    op.execute("DROP POLICY IF EXISTS documents_tenant_isolation_select ON documents")
    op.execute("ALTER TABLE documents DISABLE ROW LEVEL SECURITY")

    # ===========================================
    # DROP EXTENSION (optional - only if no other usage)
    # ===========================================
    # Note: Don't drop pg_stat_statements as it may be used elsewhere
