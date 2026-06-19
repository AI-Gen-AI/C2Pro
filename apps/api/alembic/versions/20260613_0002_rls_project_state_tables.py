"""Enable RLS policies for project_state tables (TASK-V3-014-07).

Enables Row-Level Security on project_states and project_state_entities
with tenant isolation policies for SELECT, INSERT, UPDATE, and DELETE.

Follows the RLS pattern established in 20260205_0001_enable_rls_policies.py:
  - Policies use app.current_tenant GUC set by middleware
  - COALESCE pattern allows superuser/admin bypass when GUC is unset

Revision ID: 20260613_0002
Revises: 20260613_0001
Create Date: 2026-06-13

Suite ID: TS-SEC-PS-RLS-001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260613_0002"
down_revision: str = "20260613_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable RLS and create tenant isolation policies on project_state tables."""

    # ── Enable RLS ─────────────────────────────────────────────────
    op.execute("ALTER TABLE project_states ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_state_entities ENABLE ROW LEVEL SECURITY")

    # ── project_states policies ────────────────────────────────────
    op.execute("""
        CREATE POLICY project_states_select ON project_states
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
    op.execute("""
        CREATE POLICY project_states_insert ON project_states
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
    op.execute("""
        CREATE POLICY project_states_update ON project_states
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
    op.execute("""
        CREATE POLICY project_states_delete ON project_states
        FOR DELETE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)

    # ── project_state_entities policies ────────────────────────────
    op.execute("""
        CREATE POLICY pse_select ON project_state_entities
        FOR SELECT
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
    op.execute("""
        CREATE POLICY pse_insert ON project_state_entities
        FOR INSERT
        WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
    op.execute("""
        CREATE POLICY pse_update ON project_state_entities
        FOR UPDATE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)
    op.execute("""
        CREATE POLICY pse_delete ON project_state_entities
        FOR DELETE
        USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id))
    """)


def downgrade() -> None:
    """Remove RLS policies and disable RLS on project_state tables."""

    op.execute("DROP POLICY IF EXISTS project_states_select ON project_states")
    op.execute("DROP POLICY IF EXISTS project_states_insert ON project_states")
    op.execute("DROP POLICY IF EXISTS project_states_update ON project_states")
    op.execute("DROP POLICY IF EXISTS project_states_delete ON project_states")

    op.execute("DROP POLICY IF EXISTS pse_select ON project_state_entities")
    op.execute("DROP POLICY IF EXISTS pse_insert ON project_state_entities")
    op.execute("DROP POLICY IF EXISTS pse_update ON project_state_entities")
    op.execute("DROP POLICY IF EXISTS pse_delete ON project_state_entities")

    op.execute("ALTER TABLE project_state_entities DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_states DISABLE ROW LEVEL SECURITY")
