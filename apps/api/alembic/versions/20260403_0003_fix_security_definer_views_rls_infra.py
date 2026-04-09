"""
Fix SECURITY DEFINER views and enable RLS on infrastructure tables

Revision ID: 20260403_0003
Revises: 20260403_0002
Create Date: 2026-04-03 00:03:00.000000

Fixes:
- 8 views using SECURITY DEFINER → SECURITY INVOKER
- 6 infrastructure tables missing RLS (alembic_version, checkpoint_*)
- All views use strict fail-closed NULLIF pattern (no COALESCE)
- Dynamically detects column existence to handle schema drift

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
    # All views use dynamic PL/pgSQL to detect columns at runtime
    # This handles schema drift between different database states

    # --- v_project_stakeholders ---
    op.execute("DROP VIEW IF EXISTS v_project_stakeholders")
    op.execute(
        """
        DO $$
        DECLARE
            has_quadrant boolean;
            has_source_clause boolean;
            has_clause_code boolean;
        BEGIN
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'stakeholders' AND column_name = 'quadrant'
            ) INTO has_quadrant;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'stakeholders' AND column_name = 'source_clause_id'
            ) INTO has_source_clause;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'clauses' AND column_name = 'clause_code'
            ) INTO has_clause_code;

            EXECUTE format(
                $sql$
                CREATE VIEW v_project_stakeholders AS
                SELECT
                    s.id,
                    s.project_id,
                    p.tenant_id,
                    s.name,
                    s.role,
                    s.organization,
                    %s,
                    %s,
                    s.created_at
                FROM stakeholders s
                JOIN projects p ON p.id = s.project_id
                %s
                WHERE s.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                $sql$,
                CASE WHEN has_quadrant THEN 's.quadrant' ELSE 'NULL::text' END,
                CASE WHEN has_source_clause AND has_clause_code THEN 'c.clause_code' ELSE 'NULL::text' END,
                CASE WHEN has_source_clause THEN 'LEFT JOIN clauses c ON c.id = s.source_clause_id' ELSE '' END
            );
        END
        $$;
        """
    )
    op.execute("ALTER VIEW v_project_stakeholders SET (security_invoker = true)")

    # --- v_raci_matrix ---
    op.execute("DROP VIEW IF EXISTS v_raci_matrix")
    # Ensure evidence_text column exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'stakeholder_wbs_raci' AND column_name = 'evidence_text'
            ) THEN
                ALTER TABLE stakeholder_wbs_raci ADD COLUMN evidence_text TEXT;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            wbs_code_expr text;
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'wbs_code'
            ) THEN
                wbs_code_expr := 'w.wbs_code';
            ELSE
                wbs_code_expr := 'w.code';
            END IF;

            EXECUTE format(
                $sql$
                CREATE VIEW v_raci_matrix AS
                SELECT
                    r.id,
                    r.project_id,
                    p.tenant_id,
                    r.stakeholder_id,
                    s.name AS stakeholder_name,
                    r.wbs_item_id,
                    %s AS wbs_code,
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
                $sql$,
                wbs_code_expr
            );
        END
        $$;
        """
    )
    op.execute("ALTER VIEW v_raci_matrix SET (security_invoker = true)")

    # --- v_coherence_breakdown ---
    op.execute("DROP VIEW IF EXISTS v_coherence_breakdown")
    op.execute(
        """
        DO $$
        DECLARE
            has_updated_at boolean;
        BEGIN
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'analyses' AND column_name = 'updated_at'
            ) INTO has_updated_at;

            EXECUTE format(
                $sql$
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
                    %s
                FROM analyses a
                JOIN projects p ON p.id = a.project_id
                WHERE a.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                $sql$,
                CASE WHEN has_updated_at THEN 'a.updated_at' ELSE 'NULL::timestamp' END
            );
        END
        $$;
        """
    )
    op.execute("ALTER VIEW v_coherence_breakdown SET (security_invoker = true)")

    # --- v_project_wbs ---
    op.execute("DROP VIEW IF EXISTS v_project_wbs")
    op.execute(
        """
        DO $$
        DECLARE
            wbs_code_expr text;
            has_updated_at boolean;
            has_description boolean;
            has_item_type boolean;
            has_source_clause boolean;
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'wbs_code'
            ) THEN
                wbs_code_expr := 'w.wbs_code';
            ELSE
                wbs_code_expr := 'w.code';
            END IF;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'updated_at'
            ) INTO has_updated_at;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'description'
            ) INTO has_description;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'item_type'
            ) INTO has_item_type;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'source_clause_id'
            ) INTO has_source_clause;

            EXECUTE format(
                $sql$
                CREATE VIEW v_project_wbs AS
                SELECT
                    w.id,
                    w.project_id,
                    p.tenant_id,
                    w.parent_id,
                    %s AS wbs_code,
                    w.name AS title,
                    %s,
                    w.level,
                    %s,
                    w.planned_start AS start_date,
                    w.planned_end AS end_date,
                    %s,
                    w.created_at,
                    %s
                FROM wbs_items w
                JOIN projects p ON p.id = w.project_id
                WHERE w.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                $sql$,
                wbs_code_expr,
                CASE WHEN has_description THEN 'w.description' ELSE 'NULL::text' END,
                CASE WHEN has_item_type THEN 'w.item_type' ELSE 'NULL::text' END,
                CASE WHEN has_source_clause THEN 'w.source_clause_id' ELSE 'NULL::uuid' END,
                CASE WHEN has_updated_at THEN 'w.updated_at' ELSE 'NULL::timestamp' END
            );
        END
        $$;
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
        DO $$
        DECLARE
            has_category boolean;
            has_rule_id boolean;
            has_description boolean;
            has_source_clause boolean;
            has_clause_code boolean;
        BEGIN
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'category'
            ) INTO has_category;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'rule_id'
            ) INTO has_rule_id;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'description'
            ) INTO has_description;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'source_clause_id'
            ) INTO has_source_clause;

            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'clauses' AND column_name = 'clause_code'
            ) INTO has_clause_code;

            EXECUTE format(
                $sql$
                CREATE VIEW v_project_alerts AS
                SELECT
                    a.id,
                    a.project_id,
                    p.tenant_id,
                    a.severity,
                    %s AS category,
                    %s AS rule_id,
                    a.title,
                    %s AS description,
                    a.status,
                    %s AS source_clause_id,
                    %s AS clause_code,
                    a.created_at
                FROM alerts a
                JOIN projects p ON p.id = a.project_id
                %s
                WHERE a.status = 'open'
                  AND a.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                $sql$,
                CASE WHEN has_category THEN 'a.category' ELSE 'NULL::text' END,
                CASE WHEN has_rule_id THEN 'a.rule_id' ELSE 'NULL::text' END,
                CASE WHEN has_description THEN 'a.description' ELSE 'NULL::text' END,
                CASE WHEN has_source_clause THEN 'a.source_clause_id' ELSE 'NULL::uuid' END,
                CASE WHEN has_source_clause AND has_clause_code THEN 'c.clause_code' ELSE 'NULL::text' END,
                CASE WHEN has_source_clause THEN 'LEFT JOIN clauses c ON c.id = a.source_clause_id' ELSE '' END
            );
        END
        $$;
        """
    )
    op.execute("ALTER VIEW v_project_alerts SET (security_invoker = true)")

    # --- v_project_bom ---
    op.execute("DROP VIEW IF EXISTS v_project_bom")
    op.execute(
        """
        DO $$
        DECLARE
            bom_table text;
            bom_unit_expr text;
            bom_total_expr text;
            bom_clause_expr text;
            bom_created_expr text;
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'procurement_bom_items'
            ) THEN
                bom_table := 'procurement_bom_items';
                bom_unit_expr := 'b.unit';
                bom_total_expr := 'b.total_price';
                bom_clause_expr := 'b.contract_clause_id';
                bom_created_expr := 'NULL::timestamp without time zone';
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'bom_items'
            ) THEN
                bom_table := 'bom_items';
                bom_unit_expr := 'b.unit';
                bom_total_expr := 'b.total_price';
                bom_clause_expr := 'b.contract_clause_id';
                bom_created_expr := 'b.created_at';
            ELSE
                EXECUTE $sql$
                CREATE VIEW v_project_bom AS
                SELECT
                    NULL::uuid AS id,
                    NULL::uuid AS project_id,
                    NULL::uuid AS tenant_id,
                    NULL::uuid AS wbs_item_id,
                    NULL::text AS item_code,
                    NULL::text AS item_name,
                    NULL::text AS description,
                    NULL::text AS category,
                    NULL::numeric AS quantity,
                    NULL::text AS unit_of_measure,
                    NULL::numeric AS total_cost,
                    NULL::text AS procurement_status,
                    NULL::uuid AS source_clause_id,
                    NULL::timestamp without time zone AS created_at
                WHERE false;
                $sql$;
                RETURN;
            END IF;

            EXECUTE format(
                $sql$
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
                    %s AS unit_of_measure,
                    %s AS total_cost,
                    b.procurement_status,
                    %s AS source_clause_id,
                    %s AS created_at
                FROM %I b
                JOIN projects p ON p.id = b.project_id
                WHERE b.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                $sql$,
                bom_unit_expr,
                bom_total_expr,
                bom_clause_expr,
                bom_created_expr,
                bom_table
            );
        END
        $$;
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
    op.execute("DROP VIEW IF EXISTS v_project_stakeholders")
    op.execute("DROP VIEW IF EXISTS v_raci_matrix")
    op.execute("DROP VIEW IF EXISTS v_coherence_breakdown")
    op.execute("DROP VIEW IF EXISTS v_project_wbs")
    op.execute("DROP VIEW IF EXISTS v_project_clauses")
    op.execute("DROP VIEW IF EXISTS v_project_alerts")
    op.execute("DROP VIEW IF EXISTS v_project_bom")
    op.execute("DROP VIEW IF EXISTS v_project_summary")

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
