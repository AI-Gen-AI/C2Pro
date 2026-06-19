"""Add document_revisions table for content-addressed lineage (ADR-015 / TASK-V3-015-01).

Creates the append-only document_revisions table with:
  - Content-addressed blob storage (blob_hash + blob_key)
  - rev_no monotonic per document
  - Self-referencing parent_revision_id for lineage chain
  - Partial unique constraint: at most one open revision (valid_to IS NULL) per document
  - RLS policies matching the app.current_tenant COALESCE precedent

Revision ID: 20260613_0003
Revises: 20260613_0002
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260613_0003"
down_revision: str = "20260613_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '30s';")

    op.execute(
        """
        CREATE TABLE document_revisions (
            revision_id         UUID PRIMARY KEY,
            document_id         UUID NOT NULL
                                REFERENCES documents (id) ON DELETE CASCADE,
            project_id          UUID NOT NULL,
            tenant_id           UUID NOT NULL,
            rev_no              INT NOT NULL,
            parent_revision_id  UUID
                                REFERENCES document_revisions (revision_id) ON DELETE SET NULL,
            blob_hash           VARCHAR(64) NOT NULL,
            blob_key            TEXT NOT NULL,
            valid_from          TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            valid_to            TIMESTAMP WITHOUT TIME ZONE,
            created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),

            CONSTRAINT uq_docrev_document_revno UNIQUE (document_id, rev_no)
        );
        """
    )

    op.execute(
        "CREATE INDEX ix_docrev_document ON document_revisions (document_id);"
    )
    op.execute(
        "CREATE INDEX ix_docrev_tenant ON document_revisions (tenant_id);"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_docrev_open_revision
            ON document_revisions (document_id)
            WHERE valid_to IS NULL;
        """
    )

    # RLS policies
    op.execute("ALTER TABLE document_revisions ENABLE ROW LEVEL SECURITY")

    policy_using = (
        "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)"
    )
    op.execute(
        f"CREATE POLICY docrev_select ON document_revisions FOR SELECT USING ({policy_using})"
    )
    op.execute(
        f"CREATE POLICY docrev_insert ON document_revisions FOR INSERT WITH CHECK ({policy_using})"
    )
    op.execute(
        f"CREATE POLICY docrev_update ON document_revisions FOR UPDATE USING ({policy_using})"
    )
    op.execute(
        f"CREATE POLICY docrev_delete ON document_revisions FOR DELETE USING ({policy_using})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS docrev_select ON document_revisions")
    op.execute("DROP POLICY IF EXISTS docrev_insert ON document_revisions")
    op.execute("DROP POLICY IF EXISTS docrev_update ON document_revisions")
    op.execute("DROP POLICY IF EXISTS docrev_delete ON document_revisions")
    op.execute("ALTER TABLE document_revisions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TABLE IF EXISTS document_revisions")
