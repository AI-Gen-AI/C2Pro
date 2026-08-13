"""add source document linkage for parsed WBS rows.

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-13

TASK-DOC-WBS-ORPHAN-IDEM: schedule re-parses must replace the WBS rows produced
by the same source document instead of colliding on
``uq_procurement_wbs_project_code``, and deleting a document must cascade to its
schedule-derived WBS rows so orphaned activities no longer inflate the audit.

Mirrors the BOM linkage added in 20260628_0001. Adds a real FK column with
ON DELETE CASCADE and backfills it from the ``source_document_id`` previously
kept only inside ``wbs_metadata`` (JSONB).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "procurement_wbs_items",
        sa.Column("source_document_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_procurement_wbs_items_source_document",
        "procurement_wbs_items",
        "documents",
        ["source_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_procurement_wbs_project_source_document",
        "procurement_wbs_items",
        ["project_id", "source_document_id"],
    )
    # Backfill the new FK column from the source_document_id previously stored in
    # wbs_metadata (JSONB), but only where the referenced document still exists.
    # Rows pointing at a deleted (or non-UUID) document remain NULL — those are
    # true orphans or manual/AI-generated rows and must not gain a dangling FK.
    op.execute(
        """
        UPDATE procurement_wbs_items AS w
        SET source_document_id = sub.doc_id
        FROM (
            SELECT wi.id AS wbs_id,
                   (wi.wbs_metadata->>'source_document_id')::uuid AS doc_id
            FROM procurement_wbs_items wi
            WHERE wi.source_document_id IS NULL
              AND wi.wbs_metadata ? 'source_document_id'
              AND wi.wbs_metadata->>'source_document_id'
                    ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        ) AS sub
        JOIN documents d ON d.id = sub.doc_id
        WHERE w.id = sub.wbs_id
        """
    )


def downgrade() -> None:
    op.drop_index(
        "idx_procurement_wbs_project_source_document",
        table_name="procurement_wbs_items",
    )
    op.drop_constraint(
        "fk_procurement_wbs_items_source_document",
        "procurement_wbs_items",
        type_="foreignkey",
    )
    op.drop_column("procurement_wbs_items", "source_document_id")
