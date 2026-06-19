"""Add project_snapshots append-only read model (ADR-015 / TASK-V3-015-04).

Creates project_snapshots as the cheap temporal read model:
  - opaque health_vector JSONB supplied by callers
  - optional lineage to project_events
  - DB-enforced INSERT-only behavior for updates; retention may delete later
  - RLS policies using app.current_tenant COALESCE precedent

Revision ID: 20260614_0002
Revises: 20260614_0001
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_0002"
down_revision: str = "20260614_0001"
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
        CREATE TABLE project_snapshots (
            snapshot_id          UUID PRIMARY KEY,
            project_id           UUID NOT NULL,
            tenant_id            UUID NOT NULL,
            captured_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            trigger              VARCHAR(40) NOT NULL,
            health_vector        JSONB NOT NULL,
            coherence_subscore   DOUBLE PRECISION,
            counts               JSONB NOT NULL DEFAULT '{}'::jsonb,
            totals               JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_event_id      UUID
                                  REFERENCES project_events (event_id)
                                  ON DELETE SET NULL,
            created_at           TIMESTAMP WITHOUT TIME ZONE NOT NULL
                                  DEFAULT (now() AT TIME ZONE 'utc'),

            CONSTRAINT ck_project_snapshots_trigger
                CHECK (
                    trigger IN (
                        'revision_ingested',
                        'graph_completed',
                        'hitl_correction',
                        'scheduled',
                        'baseline_changed'
                    )
                )
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_project_snapshots_project_captured "
        "ON project_snapshots (project_id, captured_at);"
    )
    op.execute(
        "CREATE INDEX ix_project_snapshots_tenant_id ON project_snapshots (tenant_id);"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_project_snapshots_update()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'project_snapshots is insert-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_project_snapshots_immutable
        BEFORE UPDATE ON project_snapshots
        FOR EACH ROW EXECUTE FUNCTION prevent_project_snapshots_update();
        """
    )

    op.execute("ALTER TABLE project_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY project_snapshots_select ON project_snapshots "
        f"FOR SELECT USING ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY project_snapshots_insert ON project_snapshots "
        f"FOR INSERT WITH CHECK ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY project_snapshots_update ON project_snapshots "
        f"FOR UPDATE USING ({_POLICY_USING})"
    )
    op.execute(
        f"CREATE POLICY project_snapshots_delete ON project_snapshots "
        f"FOR DELETE USING ({_POLICY_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS project_snapshots_select ON project_snapshots")
    op.execute("DROP POLICY IF EXISTS project_snapshots_insert ON project_snapshots")
    op.execute("DROP POLICY IF EXISTS project_snapshots_update ON project_snapshots")
    op.execute("DROP POLICY IF EXISTS project_snapshots_delete ON project_snapshots")
    op.execute("ALTER TABLE project_snapshots DISABLE ROW LEVEL SECURITY")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_project_snapshots_immutable ON project_snapshots"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_project_snapshots_update")
    op.execute("DROP TABLE IF EXISTS project_snapshots")
