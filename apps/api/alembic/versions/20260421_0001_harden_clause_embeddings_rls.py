"""Harden clause_embeddings tenant isolation with fail-closed RLS.

Revision ID: 20260421_0001
Revises: 20260401_0001
Create Date: 2026-04-21 00:00:00.000000

Suite ID: TS-SEC-RLS-CLAUSE-EMBEDDINGS-001
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260421_0001"
down_revision: str = "20260401_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY_NAME = "clause_embeddings_tenant_isolation"


def upgrade() -> None:
    """Enable strict RLS on clause_embeddings without schema changes."""
    op.execute("SET LOCAL lock_timeout = '30s';")
    op.execute("ALTER TABLE clause_embeddings ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE clause_embeddings FORCE ROW LEVEL SECURITY;")
    op.execute(f"DROP POLICY IF EXISTS {_POLICY_NAME} ON clause_embeddings;")
    op.execute(
        f"""
        CREATE POLICY {_POLICY_NAME}
        ON clause_embeddings
        FOR ALL
        USING (
            EXISTS (
                SELECT 1
                FROM projects p
                WHERE p.id = clause_embeddings.project_id
                  AND p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM projects p
                WHERE p.id = clause_embeddings.project_id
                  AND p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            )
        );
        """
    )


def downgrade() -> None:
    """Rollback clause_embeddings RLS hardening."""
    op.execute(f"DROP POLICY IF EXISTS {_POLICY_NAME} ON clause_embeddings;")
    op.execute("ALTER TABLE clause_embeddings NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE clause_embeddings DISABLE ROW LEVEL SECURITY;")
