"""Reconcile Clerk hotfixes and MCP compatibility views

Revision ID: 20260319_0002
Revises: 20260319_0001
Create Date: 2026-03-19 10:20:00.000000

TS-DB-MIG-REC-001
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0002"
down_revision: str | None = "20260319_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adopt live hotfixes into a forward-only Alembic-owned compatibility layer."""
    op.execute(
        """
        ALTER TABLE IF EXISTS public.tenants
            ADD COLUMN IF NOT EXISTS clerk_org_id VARCHAR(255);
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS public.users
            ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(255);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_clerk_org_id
            ON public.tenants (clerk_org_id)
            WHERE clerk_org_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_clerk_user_id
            ON public.users (clerk_user_id)
            WHERE clerk_user_id IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW v_project_summary AS
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
        FROM projects AS p
        LEFT JOIN documents AS d ON d.project_id = p.id
        LEFT JOIN alerts AS a ON a.project_id = p.id
        LEFT JOIN stakeholders AS s ON s.project_id = p.id
        GROUP BY p.id;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW v_project_alerts AS
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
        FROM alerts AS a
        JOIN projects AS p ON p.id = a.project_id
        LEFT JOIN clauses AS c ON c.id = a.source_clause_id
        WHERE a.status = 'open';
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW v_project_clauses AS
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
        FROM clauses AS c
        JOIN projects AS p ON p.id = c.project_id;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW v_project_stakeholders AS
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
        FROM stakeholders AS s
        JOIN projects AS p ON p.id = s.project_id
        LEFT JOIN clauses AS c ON c.id = s.source_clause_id;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            wbs_code_expr text;
            wbs_name_expr text;
            wbs_start_expr text;
            wbs_end_expr text;
            wbs_clause_expr text;
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'wbs_code'
            ) THEN
                wbs_code_expr := 'w.wbs_code';
            ELSE
                wbs_code_expr := 'w.code';
            END IF;

            wbs_name_expr := 'w.name';

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'start_date'
            ) THEN
                wbs_start_expr := 'w.start_date';
            ELSE
                wbs_start_expr := 'w.planned_start';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'end_date'
            ) THEN
                wbs_end_expr := 'w.end_date';
            ELSE
                wbs_end_expr := 'w.planned_end';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'source_clause_id'
            ) THEN
                wbs_clause_expr := 'w.source_clause_id';
            ELSE
                wbs_clause_expr := 'w.funded_by_clause_id';
            END IF;

            EXECUTE format(
                $sql$
                CREATE OR REPLACE VIEW v_project_wbs AS
                SELECT
                    w.id,
                    w.project_id,
                    p.tenant_id,
                    w.parent_id,
                    %s AS wbs_code,
                    %s AS title,
                    w.description,
                    w.level,
                    w.item_type,
                    %s AS start_date,
                    %s AS end_date,
                    %s AS source_clause_id,
                    w.created_at,
                    w.updated_at
                FROM wbs_items AS w
                JOIN projects AS p ON p.id = w.project_id;
                $sql$,
                wbs_code_expr,
                wbs_name_expr,
                wbs_start_expr,
                wbs_end_expr,
                wbs_clause_expr
            );
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            bom_table_name text;
            bom_unit_expr text;
            bom_total_expr text;
            bom_clause_expr text;
            bom_created_expr text;
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'bom_items'
            ) THEN
                bom_table_name := 'bom_items';
                bom_unit_expr := 'b.unit';
                bom_total_expr := 'b.total_price';
                bom_created_expr := 'b.created_at';
                bom_clause_expr := CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'bom_items' AND column_name = 'source_clause_id'
                    )
                    THEN 'b.source_clause_id'
                    ELSE 'b.contract_clause_id'
                END;
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'procurement_bom_items'
            ) THEN
                bom_table_name := 'procurement_bom_items';
                bom_unit_expr := 'b.unit';
                bom_total_expr := 'b.total_price';
                bom_clause_expr := 'b.contract_clause_id';
                bom_created_expr := 'NULL::timestamp without time zone';
            ELSE
                EXECUTE $sql$
                CREATE OR REPLACE VIEW v_project_bom AS
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
                CREATE OR REPLACE VIEW v_project_bom AS
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
                FROM %I AS b
                JOIN projects AS p ON p.id = b.project_id;
                $sql$,
                bom_unit_expr,
                bom_total_expr,
                bom_clause_expr,
                bom_created_expr,
                bom_table_name
            );
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            wbs_code_expr text;
            wbs_name_expr text;
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'wbs_items' AND column_name = 'wbs_code'
            ) THEN
                wbs_code_expr := 'w.wbs_code';
            ELSE
                wbs_code_expr := 'w.code';
            END IF;

            wbs_name_expr := 'w.name';

            EXECUTE format(
                $sql$
                CREATE OR REPLACE VIEW v_raci_matrix AS
                SELECT
                    r.id,
                    r.project_id,
                    p.tenant_id,
                    r.stakeholder_id,
                    s.name AS stakeholder_name,
                    r.wbs_item_id,
                    %s AS wbs_code,
                    %s AS wbs_title,
                    r.raci_role,
                    r.evidence_text,
                    r.generated_automatically,
                    r.manually_verified,
                    r.created_at
                FROM stakeholder_wbs_raci AS r
                JOIN projects AS p ON p.id = r.project_id
                JOIN stakeholders AS s ON s.id = r.stakeholder_id
                LEFT JOIN wbs_items AS w ON w.id = r.wbs_item_id;
                $sql$,
                wbs_code_expr,
                wbs_name_expr
            );
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW v_coherence_breakdown AS
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
        FROM analyses AS a
        JOIN projects AS p ON p.id = a.project_id;
        """
    )


def downgrade() -> None:
    """Remove MCP compatibility views added by this reconciliation revision."""
    op.execute("DROP VIEW IF EXISTS v_coherence_breakdown;")
    op.execute("DROP VIEW IF EXISTS v_raci_matrix;")
    op.execute("DROP VIEW IF EXISTS v_project_bom;")
    op.execute("DROP VIEW IF EXISTS v_project_wbs;")
    op.execute("DROP VIEW IF EXISTS v_project_stakeholders;")
    op.execute("DROP VIEW IF EXISTS v_project_clauses;")
    op.execute("DROP VIEW IF EXISTS v_project_alerts;")
    op.execute("DROP VIEW IF EXISTS v_project_summary;")
