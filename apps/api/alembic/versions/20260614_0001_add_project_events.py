"""Add project_events append-only log (ADR-015 / TASK-V3-015-03).

Creates project_events as the source of truth for project change events:
  - JSONB payload and INV-1 evidence refs
  - optional source_revision_id lineage to document_revisions
  - DB-enforced append-only behavior via trigger
  - RLS policies using app.current_tenant COALESCE precedent

Revision ID: 20260614_0001
Revises: 20260613_0003
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_0001"
down_revision: str = "20260613_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY_USING = (
    "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), "
    "'')::uuid, tenant_id)"
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '30s';")

    op.execute(
        """
        CREATE TABLE project_events (
            event_id            UUID PRIMARY KEY,
            project_id           UUID NOT NULL,
            tenant_id            UUID NOT NULL,
            event_type           VARCHAR(80) NOT NULL,
            payload              JSONB NOT NULL,
            actor                TEXT,
            confidence           DOUBLE PRECISION,
            source_revision_id   UUID
                                  REFERENCES document_revisions (revision_id)
                                  ON DELETE SET NULL,
            evidence_refs        JSONB NOT NULL DEFAULT '[]'::jsonb,
            occurred_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            created_at           TIMESTAMP WITHOUT TIME ZONE NOT NULL
                                  DEFAULT (now() AT TIME ZONE 'utc')
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_project_events_project_occurred "
        "ON project_events (project_id, occurred_at);"
    )
    op.execute("CREATE INDEX ix_project_events_tenant_id ON project_events (tenant_id);")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_project_events_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'project_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_project_events_immutable
        BEFORE UPDATE OR DELETE ON project_events
        FOR EACH ROW EXECUTE FUNCTION prevent_project_events_mutation();
        """
    )

    op.execute("ALTER TABLE project_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY project_events_select ON project_events "
        f"FOR SELECT USING ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY project_events_insert ON project_events "
        f"FOR INSERT WITH CHECK ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY project_events_update ON project_events "
        f"FOR UPDATE USING ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY project_events_delete ON project_events "
        f"FOR DELETE USING ({_POLICY_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS project_events_select ON project_events")
    op.execute("DROP POLICY IF EXISTS project_events_insert ON project_events")
    op.execute("DROP POLICY IF EXISTS project_events_update ON project_events")
    op.execute("DROP POLICY IF EXISTS project_events_delete ON project_events")
    op.execute("ALTER TABLE project_events DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER IF EXISTS trg_project_events_immutable ON project_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_project_events_mutation")
    op.execute("DROP TABLE IF EXISTS project_events")
