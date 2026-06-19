"""Add document_artifacts table for ADR-017 ProjectGraph.

Revision ID: 20260614_0004
Revises: 20260614_0003
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_0004"
down_revision: str = "20260614_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY_USING = (
    "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), "
    "'')::uuid, tenant_id)"
)


def _install_policies() -> None:
    op.execute("ALTER TABLE document_artifacts ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY document_artifacts_select ON document_artifacts "
        f"FOR SELECT USING ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY document_artifacts_insert ON document_artifacts "
        f"FOR INSERT WITH CHECK ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY document_artifacts_update ON document_artifacts "
        f"FOR UPDATE USING ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY document_artifacts_delete ON document_artifacts "
        f"FOR DELETE USING ({_POLICY_USING})"
    )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '30s';")
    op.execute(
        """
        CREATE TABLE document_artifacts (
            artifact_id UUID PRIMARY KEY,
            document_id UUID NOT NULL,
            document_revision_id UUID NULL
                REFERENCES document_revisions (revision_id) ON DELETE SET NULL,
            project_id UUID NOT NULL,
            tenant_id UUID NOT NULL,
            payload JSONB NOT NULL,
            lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
                DEFAULT (now() AT TIME ZONE 'utc'),

            CONSTRAINT ck_document_artifacts_lifecycle
                CHECK (lifecycle_status IN ('active','superseded'))
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_document_artifacts_project_lifecycle "
        "ON document_artifacts (project_id, lifecycle_status)"
    )
    op.execute("CREATE INDEX ix_document_artifacts_tenant_id ON document_artifacts (tenant_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_document_artifacts_active_document "
        "ON document_artifacts (document_id) WHERE lifecycle_status = 'active'"
    )
    _install_policies()


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_artifacts_select ON document_artifacts")
    op.execute("DROP POLICY IF EXISTS document_artifacts_insert ON document_artifacts")
    op.execute("DROP POLICY IF EXISTS document_artifacts_update ON document_artifacts")
    op.execute("DROP POLICY IF EXISTS document_artifacts_delete ON document_artifacts")
    op.execute("ALTER TABLE document_artifacts DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TABLE IF EXISTS document_artifacts")
