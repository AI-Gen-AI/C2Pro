"""Add isolated persistence for Coherence v2 shadow outputs.

Revision ID: 20260805_0001
Revises: 20260708_0001
Create Date: 2026-08-05

TASK-COH-V2-SCORE-VERSION-PERSIST: retain v2 shadow metrics without allowing
the production v1 ``coherence_results`` read path to see shadow scores.

Refers to Suite ID: TS-INT-COH-V2-SHADOW-PERSIST-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260805_0001"
down_revision: str | None = "20260708_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "coherence_v2_shadow"
_POLICY = "coherence_v2_shadow_tenant_isolation"
_TENANT_GUARD = """
    tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    AND project_id IN (
        SELECT id
        FROM projects
        WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
"""


def _reassert_tenant_rls() -> None:
    """Apply fail-closed tenant policy with idempotent policy replacement."""
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {_TABLE}")
    op.execute(
        f"""
        CREATE POLICY {_POLICY}
            ON {_TABLE}
            FOR ALL
            USING ({_TENANT_GUARD})
            WITH CHECK ({_TENANT_GUARD})
        """
    )


def upgrade() -> None:
    """Create the additive, RLS-protected v2-only shadow ledger."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coherence_v2_shadow (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            tenant_id uuid NOT NULL,
            coherence_score double precision NULL,
            completeness_score double precision NOT NULL,
            technical_reliability_index double precision NOT NULL,
            active_weight double precision NOT NULL,
            score_version varchar(32) NOT NULL DEFAULT 'coherence-v2',
            status varchar(64) NOT NULL,
            score_reason text NULL,
            categories_v2 jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_coherence_v2_shadow_score_version
                CHECK (score_version = 'coherence-v2')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_coherence_v2_shadow_tenant_project_created
            ON coherence_v2_shadow (tenant_id, project_id, created_at DESC)
        """
    )
    _reassert_tenant_rls()


def downgrade() -> None:
    """Remove only the additive shadow ledger; no v1 data is affected."""
    op.execute("DROP TABLE IF EXISTS coherence_v2_shadow")
