"""add source document linkage for parsed BOM rows.

Revision ID: 20260628_0001
Revises: 20260627_0001
Create Date: 2026-06-28

TASK-COH-BUD-IDEM-003: budget re-parses must replace the rows produced by the
same source document instead of appending duplicates.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260628_0001"
down_revision: str | None = "20260627_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROJECT_GUARD = """
    project_id IN (
        SELECT id
        FROM projects
        WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
"""


def _reassert_bom_rls_policy() -> None:
    op.execute("ALTER TABLE procurement_bom_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE procurement_bom_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_procurement_bom_items ON procurement_bom_items"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_procurement_bom_items
            ON procurement_bom_items
            FOR ALL
            USING ({PROJECT_GUARD})
            WITH CHECK ({PROJECT_GUARD});
        """
    )


def upgrade() -> None:
    op.add_column(
        "procurement_bom_items",
        sa.Column("source_document_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_procurement_bom_items_source_document",
        "procurement_bom_items",
        "documents",
        ["source_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_procurement_bom_project_source_document",
        "procurement_bom_items",
        ["project_id", "source_document_id"],
    )
    _reassert_bom_rls_policy()


def downgrade() -> None:
    op.drop_index(
        "idx_procurement_bom_project_source_document",
        table_name="procurement_bom_items",
    )
    op.drop_constraint(
        "fk_procurement_bom_items_source_document",
        "procurement_bom_items",
        type_="foreignkey",
    )
    op.drop_column("procurement_bom_items", "source_document_id")
    _reassert_bom_rls_policy()
