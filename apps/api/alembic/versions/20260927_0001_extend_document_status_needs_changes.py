"""Extend document_status enum with 'needs_changes' (#712).

Revision ID: 20260927_0001
Revises: 20260923_0001
Create Date: 2026-09-27

A HITL reviewer rejecting a document's pending analysis previously left
documents.upload_status stuck at 'parsed_pending_analysis' forever -- the
Documents UI could not distinguish "rejected, needs a human correction" from
"analysis still pending a decision". finalize_v3's reject path now sets
upload_status = 'needs_changes', so the PostgreSQL enum must carry that value.
Same idempotent single-value pattern as 20260813_0001 (clausetype 'warranty').
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0001"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'needs_changes'"))


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for enums; downgrade is intentionally a no-op.
    # The extra value is harmless and removal would require recreating the type.
    pass
