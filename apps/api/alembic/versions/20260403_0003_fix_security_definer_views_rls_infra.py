"""
Fix SECURITY DEFINER views and enable RLS on infrastructure tables

Revision ID: 20260403_0003
Revises: 20260403_0002
Create Date: 2026-04-03 00:03:00.000000

Fixes:
- 8 views using SECURITY DEFINER → SECURITY INVOKER
- 6 infrastructure tables missing RLS (alembic_version, checkpoint_*)
- All views use strict fail-closed NULLIF pattern (no COALESCE)
- Preserves exact column structure of existing views

Suite ID: TS-DB-MIG-RLS-003
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260403_0003"
down_revision: str = "20260403_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ===========================================
    # 1. Enable RLS on infrastructure tables
    # ===========================================
    # These tables have no tenant_id/project_id - use SELECT-only policy
    # so Supabase linter passes while not breaking alembic/langgraph ops

    infra_tables = [
        "schema_migrations",
        "alembic_version",
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
    ]

    for table in infra_tables:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = '{table}'
                ) THEN
                    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                    DROP POLICY IF EXISTS "{table}_select" ON {table};
                    CREATE POLICY "{table}_select" ON {table}
                        FOR SELECT USING (true);
                END IF;
            END $$;
            """
        )

    # ===========================================
    # 2. Fix SECURITY DEFINER views → SECURITY INVOKER
    # ===========================================
    # All views use strict fail-closed NULLIF pattern (NO COALESCE)
    # Column structure preserved from existing view definitions

    # --- v_project_stakeholders ---
    op.execute("DROP VIEW IF EXISTS v_project_stakeholders")
    op.execute(
        """
        CREATE VIEW v_project_stakeholders AS
        SELECT
            s.id,
            s.project_id,
            p.tenant_id,
            s.name,
            s.role,
            s.organization,
            s.quadrant,
            s.source_clause_id,
            c.clause_code,
            s.created_at
        FROM stakeholders s
        JOIN projects p ON p.id = s.project_id
        LEFT JOIN clauses c ON c.id = s.source_clause_id
        WHERE s.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_project_stakeholders SET (security_invoker = true)")

    # --- v_raci_matrix ---
    op.execute("DROP VIEW IF EXISTS v_raci_matrix")
    op.execute(
        """
        CREATE VIEW v_raci_matrix AS
        SELECT
            r.id,
            r.project_id,
            p.tenant_id,
            r.stakeholder_id,
            s.name AS stakeholder_name,
            r.wbs_item_id,
            w.code AS wbs_code,
            w.name AS wbs_title,
            r.raci_role,
            r.evidence_text,
            r.generated_automatically,
            r.manually_verified,
            r.created_at
        FROM stakeholder_wbs_raci r
        JOIN projects p ON p.id = r.project_id
        JOIN stakeholders s ON s.id = r.stakeholder_id
        LEFT JOIN wbs_items w ON w.id = r.wbs_item_id
        WHERE r.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_raci_matrix SET (security_invoker = true)")

    # --- v_coherence_breakdown ---
    # Existing view reads from analyses table (not coherence_results)
    op.execute("DROP VIEW IF EXISTS v_coherence_breakdown")
    op.execute(
        """
        CREATE VIEW v_coherence_breakdown AS
        SELECT
            a.id AS analysis_id,
            a.project_id,
            p.tenant_id,
            a.analysis_type,
            a.status,
            a.coherence_score,
            a.alerts_count,
            a.coherence_breakdown,
            a.completed_at,
            a.created_at,
            a.updated_at
        FROM analyses a
        JOIN projects p ON p.id = a.project_id
        WHERE a.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_coherence_breakdown SET (security_invoker = true)")

    # --- v_project_wbs ---
    op.execute("DROP VIEW IF EXISTS v_project_wbs")
    op.execute(
        """
        CREATE VIEW v_project_wbs AS
        SELECT
            w.id,
            w.project_id,
            p.tenant_id,
            w.parent_id,
            w.code AS wbs_code,
            w.name AS title,
            w.description,
            w.level,
            w.item_type,
            w.planned_start AS start_date,
            w.planned_end AS end_date,
            w.source_clause_id,
            w.created_at,
            w.updated_at
        FROM wbs_items w
        JOIN projects p ON p.id = w.project_id
        WHERE w.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_project_wbs SET (security_invoker = true)")

    # --- v_project_clauses ---
    op.execute("DROP VIEW IF EXISTS v_project_clauses")
    op.execute(
        """
        CREATE VIEW v_project_clauses AS
        SELECT
            c.id,
            c.project_id,
            p.tenant_id,
            c.clause_code,
            c.clause_type,
            c.title,
            c.full_text,
            c.manually_verified,
            c.created_at
        FROM clauses c
        JOIN projects p ON p.id = c.project_id
        WHERE c.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_project_clauses SET (security_invoker = true)")

    # --- v_project_alerts ---
    op.execute("DROP VIEW IF EXISTS v_project_alerts")
    op.execute(
        """
        CREATE VIEW v_project_alerts AS
        SELECT
            a.id,
            a.project_id,
            p.tenant_id,
            a.severity,
            a.category,
            a.rule_id,
            a.title,
            a.description,
            a.status,
            a.source_clause_id,
            c.clause_code,
            c.title AS clause_title,
            a.created_at
        FROM alerts a
        JOIN projects p ON p.id = a.project_id
        LEFT JOIN clauses c ON c.id = a.source_clause_id
        WHERE a.status = 'open'
          AND a.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_project_alerts SET (security_invoker = true)")

    # --- v_project_bom ---
    op.execute("DROP VIEW IF EXISTS v_project_bom")
    op.execute(
        """
        CREATE VIEW v_project_bom AS
        SELECT
            b.id,
            b.project_id,
            p.tenant_id,
            b.wbs_item_id,
            b.item_code,
            b.item_name,
            b.description,
            b.category,
            b.quantity,
            b.unit AS unit_of_measure,
            b.total_price AS total_cost,
            b.procurement_status,
            b.contract_clause_id AS source_clause_id,
            NULL::timestamp without time zone AS created_at
        FROM procurement_bom_items b
        JOIN projects p ON p.id = b.project_id
        WHERE b.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_project_bom SET (security_invoker = true)")

    # --- v_project_summary ---
    op.execute("DROP VIEW IF EXISTS v_project_summary")
    op.execute(
        """
        CREATE VIEW v_project_summary AS
        SELECT
            p.id,
            p.tenant_id,
            p.name,
            p.status,
            p.coherence_score,
            COUNT(DISTINCT d.id) AS document_count,
            COUNT(DISTINCT a.id) FILTER (WHERE a.status = 'open') AS alert_count,
            COUNT(DISTINCT s.id) AS stakeholder_count,
            p.created_at,
            p.updated_at
        FROM projects p
        LEFT JOIN documents d ON d.project_id = p.id
        LEFT JOIN alerts a ON a.project_id = p.id
        LEFT JOIN stakeholders s ON s.project_id = p.id
        WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        GROUP BY p.id
        """
    )
    op.execute("ALTER VIEW v_project_summary SET (security_invoker = true)")


def downgrade() -> None:
    # ===========================================
    # Drop fixed views
    # ===========================================
    op.execute("DROP VIEW IF EXISTS v_project_stakeholders")
    op.execute("DROP VIEW IF EXISTS v_raci_matrix")
    op.execute("DROP VIEW IF EXISTS v_coherence_breakdown")
    op.execute("DROP VIEW IF EXISTS v_project_wbs")
    op.execute("DROP VIEW IF EXISTS v_project_clauses")
    op.execute("DROP VIEW IF EXISTS v_project_alerts")
    op.execute("DROP VIEW IF EXISTS v_project_bom")
    op.execute("DROP VIEW IF EXISTS v_project_summary")

    # ===========================================
    # Drop RLS from infrastructure tables
    # ===========================================
    infra_tables = [
        "schema_migrations",
        "alembic_version",
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
    ]

    for table in infra_tables:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = '{table}'
                ) THEN
                    DROP POLICY IF EXISTS "{table}_select" ON {table};
                    ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
                END IF;
            END $$;
            """
        )
