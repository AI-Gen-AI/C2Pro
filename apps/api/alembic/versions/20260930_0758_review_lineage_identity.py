"""#758: the processing lineage a pending review may be resumed through.

Revision ID: 20260930_0758
Revises: 20260928_0711
Create Date: 2026-09-30

``review_items.thread_id`` already names the LangGraph checkpoint lineage a
review resumes, but nothing recorded WHICH processing attempt that lineage
belonged to. So a review stayed resumable after a new revision, reprocess or
takeover had made its lineage historical -- the approval replayed superseded
evidence, and a stale ``resume_operations`` row could still finalize against
the current review and document.

These two columns carry the #711 grant that bound the lineage, stamped by the
attempt that claims it. ``src/core/resume_lineage.py`` compares them with the
document's live ``document_processing_operations`` row: equal means the
lineage is still current, different means every resume, N17 continuation,
graph-completed finalization and review/document finalization bound to it
fails closed.

Nullable with no backfill, on purpose. NULL is the honest value for a row
bound before this identity existed (production still has pending reviews on
UUID-style threads), and those rows are exempt from the comparison rather
than refused by it. ``begin_generation`` stamps a NULL row with the
generation it belonged to as it bumps, which is what makes a reupload or
reprocess supersede a legacy review too.

The composite index is not new behaviour: ``find_active_review`` and the
generation-transition stamp both address (document_id, current_status), and
``document_id`` carried only a foreign key, so both were sequential scans.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260930_0758"
down_revision: str | None = "20260928_0711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "public.review_items"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN lineage_generation bigint NULL")
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN lineage_fencing_token bigint NULL")
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_review_items_document_status "
        f"ON {_TABLE} (document_id, current_status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_review_items_document_status")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS lineage_fencing_token")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS lineage_generation")
