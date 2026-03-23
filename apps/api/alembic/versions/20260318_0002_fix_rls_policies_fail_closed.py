"""Fix RLS policies to fail-closed pattern

Revision ID: 20260318_0002
Revises: 20260318_0001
Create Date: 2026-03-18 20:00:00.000000

SECURITY FIX:
Previous RLS policies used COALESCE(current_tenant, tenant_id) which
allowed access to ALL rows when app.current_tenant was not set.

This migration fixes policies to fail-closed:
- If app.current_tenant is not set → NO ACCESS (secure default)
- If app.current_tenant is set → filter by that tenant

References:
- C2PRO Technical Audit Report 2026-03-18
- TS-E2E-SEC-TNT-001: Multi-tenant isolation tests
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260318_0002"
down_revision: str | None = "20260318_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ===========================================================================
# FAIL-CLOSED PATTERN EXPLANATION
# ===========================================================================
#
# OLD PATTERN (PERMISSIVE - SECURITY VULNERABILITY):
#   tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)
#   → If app.current_tenant is NOT set, COALESCE returns tenant_id
#   → tenant_id = tenant_id is ALWAYS TRUE
#   → ALL ROWS ACCESSIBLE
#
# NEW PATTERN (FAIL-CLOSED - SECURE):
#   tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
#   → If app.current_tenant is NOT set, returns NULL
#   → tenant_id = NULL is ALWAYS FALSE
#   → NO ROWS ACCESSIBLE (secure default)
#
# SUPERUSER/ADMIN BYPASS:
#   Superusers and table owners bypass RLS by default.
#   Use ALTER TABLE ... FORCE ROW LEVEL SECURITY to enforce on owners.
#   For this system, we keep the default (superuser bypasses RLS).
#
# ===========================================================================


def upgrade() -> None:
    """Fix RLS policies to fail-closed pattern."""

    # ===========================================
    # PROJECTS TABLE - FIX POLICIES
    # ===========================================

    # Drop existing permissive policies
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_select ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_insert ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_update ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_delete ON projects")

    # Create fail-closed policies
    op.execute("""
        CREATE POLICY project_tenant_isolation_select ON projects
        FOR SELECT
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY project_tenant_isolation_insert ON projects
        FOR INSERT
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY project_tenant_isolation_update ON projects
        FOR UPDATE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY project_tenant_isolation_delete ON projects
        FOR DELETE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    # ===========================================
    # USERS TABLE - FIX POLICIES
    # ===========================================

    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_select ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_insert ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_update ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_delete ON users")

    op.execute("""
        CREATE POLICY user_tenant_isolation_select ON users
        FOR SELECT
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY user_tenant_isolation_insert ON users
        FOR INSERT
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY user_tenant_isolation_update ON users
        FOR UPDATE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY user_tenant_isolation_delete ON users
        FOR DELETE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    # ===========================================
    # TENANTS TABLE - FIX POLICIES
    # ===========================================

    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON tenants")
    # Note: INSERT and DELETE already use `false` which is correct

    op.execute("""
        CREATE POLICY tenant_isolation_select ON tenants
        FOR SELECT
        USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_update ON tenants
        FOR UPDATE
        USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    # ===========================================
    # REVIEW_ITEMS TABLE - FIX POLICIES
    # ===========================================

    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON review_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON review_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON review_items")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON review_items
        FOR SELECT
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_insert ON review_items
        FOR INSERT
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_update ON review_items
        FOR UPDATE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)


def downgrade() -> None:
    """Revert to original (permissive) policies - NOT RECOMMENDED for production."""

    # ===========================================
    # PROJECTS TABLE - RESTORE ORIGINAL
    # ===========================================

    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_select ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_insert ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_update ON projects")
    op.execute("DROP POLICY IF EXISTS project_tenant_isolation_delete ON projects")

    op.execute("""
        CREATE POLICY project_tenant_isolation_select ON projects
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY project_tenant_isolation_insert ON projects
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY project_tenant_isolation_update ON projects
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY project_tenant_isolation_delete ON projects
        FOR DELETE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # ===========================================
    # USERS TABLE - RESTORE ORIGINAL
    # ===========================================

    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_select ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_insert ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_update ON users")
    op.execute("DROP POLICY IF EXISTS user_tenant_isolation_delete ON users")

    op.execute("""
        CREATE POLICY user_tenant_isolation_select ON users
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY user_tenant_isolation_insert ON users
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY user_tenant_isolation_update ON users
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY user_tenant_isolation_delete ON users
        FOR DELETE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # ===========================================
    # TENANTS TABLE - RESTORE ORIGINAL
    # ===========================================

    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON tenants")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON tenants
        FOR SELECT
        USING (id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, id))
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_update ON tenants
        FOR UPDATE
        USING (id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, id))
    """)

    # ===========================================
    # REVIEW_ITEMS TABLE - RESTORE ORIGINAL
    # ===========================================

    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON review_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON review_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON review_items")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON review_items
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_insert ON review_items
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_update ON review_items
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
