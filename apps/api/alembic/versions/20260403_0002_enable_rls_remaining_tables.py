"""Enable RLS on remaining tables

Revision ID: 20260403_0002
Revises: 20260403_0001
Create Date: 2026-04-03 00:02:00.000000

TASK-1491: Extend RLS to remaining tables.

Tables covered:
- stakeholders, stakeholder_wbs_raci (project-scoped)
- procurement_wbs_items, procurement_bom_items (project-scoped)
- procurement_budget_items (orphaned -> add project_id)
- analyses, alerts (project-scoped)
- coherence_results (project-scoped)
- review_items (already has RLS, skip)
- extractions (orphaned -> add project_id)
- document_chunks, wbs_items, clause_embeddings (project-scoped)

Pattern: Strict fail-closed (NULLIF only, no COALESCE fallback).
Uses FOR ALL single policy for tables created after 20260318_0002.
Uses 4 separate policies for tables that already use that pattern.

Suite ID: TS-DB-MIG-RLS-002
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260403_0002"
down_revision: str = "20260403_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ===========================================================================
# FAIL-CLOSED PATTERN (from 20260318_0002)
# ===========================================================================
# tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
# - If app.current_tenant is NOT set -> returns NULL -> condition is FALSE
# - If app.current_tenant IS set -> filter by that tenant
# NO COALESCE fallback (that was the security vulnerability fixed in 20260318_0002)
# ===========================================================================


def upgrade() -> None:
    # ===========================================
    # FIX ORPHANED TABLES: Add project_id columns
    # ===========================================

    # procurement_budget_items: was completely orphaned from tenant/project scope
    op.execute(
        "ALTER TABLE procurement_budget_items ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE CASCADE"
    )

    # extractions: had document_id but no project_id (2-hop join was security risk)
    op.execute(
        "ALTER TABLE extractions ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE CASCADE"
    )

    # Backfill project_id for existing extractions via documents join
    op.execute(
        """
        UPDATE extractions e
        SET project_id = d.project_id
        FROM documents d
        WHERE e.document_id = d.id
          AND e.project_id IS NULL
        """
    )

    # Add index on new project_id columns for RLS performance
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_procurement_budget_items_project ON procurement_budget_items(project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_extractions_project ON extractions(project_id)"
    )

    # ===========================================
    # PROJECT-SCOPED TABLES: FOR ALL policy pattern
    # ===========================================

    project_guard = """
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    """

    # --- stakeholders ---
    op.execute("ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stakeholders FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_stakeholders ON stakeholders")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_stakeholders
            ON stakeholders
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- stakeholder_wbs_raci ---
    op.execute("ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stakeholder_wbs_raci FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_stakeholder_wbs_raci ON stakeholder_wbs_raci")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_stakeholder_wbs_raci
            ON stakeholder_wbs_raci
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- procurement_wbs_items ---
    op.execute("ALTER TABLE procurement_wbs_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE procurement_wbs_items FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_procurement_wbs_items ON procurement_wbs_items")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_procurement_wbs_items
            ON procurement_wbs_items
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- procurement_bom_items ---
    op.execute("ALTER TABLE procurement_bom_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE procurement_bom_items FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_procurement_bom_items ON procurement_bom_items")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_procurement_bom_items
            ON procurement_bom_items
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- procurement_budget_items (now has project_id) ---
    op.execute("ALTER TABLE procurement_budget_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE procurement_budget_items FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_procurement_budget_items ON procurement_budget_items")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_procurement_budget_items
            ON procurement_budget_items
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- analyses ---
    op.execute("ALTER TABLE analyses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE analyses FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_analyses ON analyses")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_analyses
            ON analyses
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- alerts ---
    op.execute("ALTER TABLE alerts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alerts FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_alerts ON alerts")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_alerts
            ON alerts
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- coherence_results ---
    op.execute("ALTER TABLE coherence_results ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE coherence_results FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_coherence_results ON coherence_results")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_coherence_results
            ON coherence_results
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- document_chunks ---
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_document_chunks ON document_chunks")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_document_chunks
            ON document_chunks
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- wbs_items ---
    op.execute("ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wbs_items FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_wbs_items ON wbs_items")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_wbs_items
            ON wbs_items
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- clause_embeddings ---
    op.execute("ALTER TABLE clause_embeddings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clause_embeddings FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_clause_embeddings ON clause_embeddings")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_clause_embeddings
            ON clause_embeddings
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    # --- extractions (now has project_id) ---
    op.execute("ALTER TABLE extractions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE extractions FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_extractions ON extractions")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_extractions
            ON extractions
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )


def downgrade() -> None:
    # ===========================================
    # DROP RLS POLICIES AND DISABLE RLS
    # ===========================================

    tables_with_for_all = [
        "stakeholders",
        "stakeholder_wbs_raci",
        "procurement_wbs_items",
        "procurement_bom_items",
        "procurement_budget_items",
        "analyses",
        "alerts",
        "coherence_results",
        "document_chunks",
        "wbs_items",
        "clause_embeddings",
        "extractions",
    ]

    for table in tables_with_for_all:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # ===========================================
    # DROP ADDED project_id COLUMNS AND INDEXES
    # ===========================================

    op.execute("DROP INDEX IF EXISTS idx_extractions_project")
    op.execute("DROP INDEX IF EXISTS idx_procurement_budget_items_project")

    op.execute("ALTER TABLE extractions DROP COLUMN IF EXISTS project_id")
    op.execute("ALTER TABLE procurement_budget_items DROP COLUMN IF EXISTS project_id")
