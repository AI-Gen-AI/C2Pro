"""Partition project_snapshots by captured_at (ADR-015 / TASK-V3-015-06).

Recreates project_snapshots as a monthly range-partitioned table. The primary
key includes captured_at because Postgres requires partition keys in unique
constraints on partitioned tables.

Revision ID: 20260614_0003
Revises: 20260614_0002
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_0003"
down_revision: str = "20260614_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY_USING = (
    "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), "
    "'')::uuid, tenant_id)"
)


def _create_partitioned_table() -> None:
    op.execute(
        """
        CREATE TABLE project_snapshots (
            snapshot_id          UUID NOT NULL,
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

            CONSTRAINT pk_project_snapshots
                PRIMARY KEY (snapshot_id, captured_at),
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
        ) PARTITION BY RANGE (captured_at);
        """
    )


def _create_partitions() -> None:
    op.execute(
        """
        CREATE TABLE project_snapshots_default
        PARTITION OF project_snapshots DEFAULT;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            month_start date := date_trunc('month', now())::date;
            partition_start date;
            partition_end date;
            partition_name text;
        BEGIN
            FOR offset_month IN 0..2 LOOP
                partition_start := (month_start + (offset_month || ' months')::interval)::date;
                partition_end := (partition_start + interval '1 month')::date;
                partition_name := format(
                    'project_snapshots_%s',
                    to_char(partition_start, 'YYYY_MM')
                );
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF project_snapshots '
                    'FOR VALUES FROM (%L) TO (%L)',
                    partition_name,
                    partition_start,
                    partition_end
                );
            END LOOP;
        END $$;
        """
    )


def _install_snapshot_policies() -> None:
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


def _install_snapshot_trigger() -> None:
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


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '30s';")
    op.execute("DROP TABLE IF EXISTS project_snapshots CASCADE")
    _create_partitioned_table()
    _create_partitions()
    op.execute(
        "CREATE INDEX ix_project_snapshots_project_captured "
        "ON project_snapshots (project_id, captured_at);"
    )
    op.execute("CREATE INDEX ix_project_snapshots_tenant_id ON project_snapshots (tenant_id);")
    _install_snapshot_trigger()
    _install_snapshot_policies()


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS project_snapshots_select ON project_snapshots")
    op.execute("DROP POLICY IF EXISTS project_snapshots_insert ON project_snapshots")
    op.execute("DROP POLICY IF EXISTS project_snapshots_update ON project_snapshots")
    op.execute("DROP POLICY IF EXISTS project_snapshots_delete ON project_snapshots")
    op.execute("ALTER TABLE project_snapshots DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER IF EXISTS trg_project_snapshots_immutable ON project_snapshots")
    op.execute("DROP FUNCTION IF EXISTS prevent_project_snapshots_update")
    op.execute("DROP TABLE IF EXISTS project_snapshots CASCADE")

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
    op.execute("CREATE INDEX ix_project_snapshots_tenant_id ON project_snapshots (tenant_id);")
    _install_snapshot_trigger()
    _install_snapshot_policies()
