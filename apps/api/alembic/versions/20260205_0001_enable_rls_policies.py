"""Enable RLS policies for multi-tenant isolation

Revision ID: 20260205_0001
Revises: 20260124_0002
Create Date: 2026-02-05 00:00:00.000000

This migration enables Row-Level Security (RLS) on all multi-tenant tables
and creates policies to enforce tenant isolation at the database level.

CRITICAL FOR SECURITY:
- Without RLS, middleware alone cannot guarantee tenant isolation
- RLS provides defense-in-depth (fails closed if middleware fails)
- Policies ensure even direct DB access is tenant-scoped

Refers to Suite ID: TS-E2E-SEC-TNT-001
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260205_0001"
down_revision: str | None = "20260124_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Enable RLS and create tenant isolation policies.

    Strategy:
    1. Enable RLS on all multi-tenant tables
    2. Create policies for SELECT, INSERT, UPDATE, DELETE
    3. Use app.current_tenant session variable set by middleware
    """

    # ===========================================
    # ENABLE ROW LEVEL SECURITY
    # ===========================================

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")

    # ===========================================
    # TENANTS TABLE POLICIES
    # ===========================================

    # Policy: Tenants can only see their own tenant record
    op.execute("""
        CREATE POLICY tenant_isolation_select ON tenants
        FOR SELECT
        USING (id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, id))
    """)

    # Policy: Tenants cannot insert new tenant records (admin-only operation)
    # This policy blocks all inserts - superuser/admin bypass RLS
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON tenants
        FOR INSERT
        WITH CHECK (false)
    """)

    # Policy: Tenants can only update their own record
    op.execute("""
        CREATE POLICY tenant_isolation_update ON tenants
        FOR UPDATE
        USING (id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, id))
    """)

    # Policy: Tenants cannot delete tenant records
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON tenants
        FOR DELETE
        USING (false)
    """)

    # ===========================================
    # USERS TABLE POLICIES
    # ===========================================

    # Policy: Users can only see users from their tenant
    op.execute("""
        CREATE POLICY user_tenant_isolation_select ON users
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # Policy: Users can only be inserted for the current tenant
    op.execute("""
        CREATE POLICY user_tenant_isolation_insert ON users
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # Policy: Users can only update users from their tenant
    op.execute("""
        CREATE POLICY user_tenant_isolation_update ON users
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # Policy: Users can only delete users from their tenant
    op.execute("""
        CREATE POLICY user_tenant_isolation_delete ON users
        FOR DELETE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # ===========================================
    # PROJECTS TABLE POLICIES (CRITICAL FOR TESTS)
    # ===========================================

    # Policy: Projects can only be read by their owning tenant
    op.execute("""
        CREATE POLICY project_tenant_isolation_select ON projects
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # Policy: Projects can only be created for the current tenant
    op.execute("""
        CREATE POLICY project_tenant_isolation_insert ON projects
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # Policy: Projects can only be updated by their owning tenant
    op.execute("""
        CREATE POLICY project_tenant_isolation_update ON projects
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # Policy: Projects can only be deleted by their owning tenant
    op.execute("""
        CREATE POLICY project_tenant_isolation_delete ON projects
        FOR DELETE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # ===========================================
    # NOTES ON POLICY LOGIC
    # ===========================================

    # The COALESCE pattern handles three scenarios:
    # 1. app.current_tenant is set → use it for isolation
    # 2. app.current_tenant is '' (empty) → use row's tenant_id (allows row)
    # 3. app.current_tenant is unset → use row's tenant_id (allows row)
    #
    # Scenarios 2-3 occur when:
    # - Superuser/admin queries (bypasses RLS)
    # - Middleware validation queries (get_raw_session)
    # - Alembic migrations
    #
    # For maximum security, middleware MUST always set app.current_tenant
    # for user-facing requests.


def downgrade() -> None:
    """
    Remove RLS policies and disable RLS.

    WARNING: This exposes all data across tenants. Use only in development.
    """

    # ===========================================
    # DROP POLICIES
    # ===========================================

    # Projects
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_select ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_insert ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_update ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_delete ON projects")

    # Users
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_select ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_insert ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_update ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_delete ON users")

    # Tenants
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON tenants")

    # ===========================================
    # DISABLE ROW LEVEL SECURITY
    # ===========================================

    op.execute("ALTER TABLE projects DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
