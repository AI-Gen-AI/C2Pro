"""Reconcile stakeholder alerts and procurement support tables

Revision ID: 20260319_0004
Revises: 20260319_0003
Create Date: 2026-03-19 11:20:00.000000

TS-DB-MIG-REC-003
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0004"
down_revision: str | None = "20260319_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adopt SQL-runner-only stakeholder/procurement support tables into Alembic."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stakeholder_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
            alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
            notification_sent BOOLEAN DEFAULT FALSE,
            notification_sent_at TIMESTAMPTZ,
            notification_method VARCHAR(50),
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            bom_table_name text;
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'bom_items'
            ) THEN
                bom_table_name := 'bom_items';
            ELSIF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'procurement_bom_items'
            ) THEN
                bom_table_name := 'procurement_bom_items';
            ELSE
                RAISE EXCEPTION
                    'Unable to reconcile bom_revisions: neither bom_items nor procurement_bom_items exists';
            END IF;

            EXECUTE format(
                $sql$
                CREATE TABLE IF NOT EXISTS bom_revisions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    bom_item_id UUID NOT NULL REFERENCES %I(id) ON DELETE CASCADE,
                    revision_number INTEGER NOT NULL,
                    changes_json JSONB NOT NULL,
                    changed_by UUID REFERENCES users(id),
                    change_reason TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT bom_revisions_item_number_unique UNIQUE (bom_item_id, revision_number)
                );
                $sql$,
                bom_table_name
            );
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS procurement_plan_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            snapshot_name VARCHAR(255) NOT NULL,
            snapshot_data JSONB NOT NULL,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stakeholder_alerts_stakeholder ON stakeholder_alerts(stakeholder_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stakeholder_alerts_alert ON stakeholder_alerts(alert_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bom_revisions_item ON bom_revisions(bom_item_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bom_revisions_created ON bom_revisions(created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_procurement_snapshots_project ON procurement_plan_snapshots(project_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_procurement_snapshots_created ON procurement_plan_snapshots(created_at DESC);
        """
    )

    op.execute("ALTER TABLE stakeholder_alerts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE bom_revisions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE procurement_plan_snapshots ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE stakeholder_alerts FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE bom_revisions FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE procurement_plan_snapshots FORCE ROW LEVEL SECURITY;")

    project_guard = """
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    """

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_stakeholder_alerts ON stakeholder_alerts;
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_stakeholder_alerts
            ON stakeholder_alerts
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_bom_revisions ON bom_revisions;
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_bom_revisions
            ON bom_revisions
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_procurement_snapshots ON procurement_plan_snapshots;
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_procurement_snapshots
            ON procurement_plan_snapshots
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )


def downgrade() -> None:
    """Remove stakeholder/procurement support tables adopted by this revision."""
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_procurement_snapshots ON procurement_plan_snapshots;"
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation_bom_revisions ON bom_revisions;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_stakeholder_alerts ON stakeholder_alerts;")
    op.execute("DROP TABLE IF EXISTS procurement_plan_snapshots;")
    op.execute("DROP TABLE IF EXISTS bom_revisions;")
    op.execute("DROP TABLE IF EXISTS stakeholder_alerts;")
