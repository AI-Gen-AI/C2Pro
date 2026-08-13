"""Extend clausetype enum with 'warranty' (produced by the contract clause extractor).

Revision ID: 20260813_0001
Revises: 20260808_0001
Create Date: 2026-08-13

The ClauseType domain enum (src/documents/domain/models.py) includes
WARRANTY = "warranty", but the PostgreSQL `clausetype` enum was missing it. The
deterministic contract-ingestion pipeline extracts clauses and INSERTs them with
clause_type = 'warranty', which failed with:

    invalid input value for enum clausetype: "warranty"

That aborted the whole clause batch insert, erroring the document parse (no
clauses persisted -> no coherence). ALTER TYPE ... ADD VALUE IF NOT EXISTS is
idempotent and safe on PostgreSQL 12+ (Supabase uses PG 15).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0001"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'warranty'"))


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for enums; downgrade is intentionally a no-op.
    # The extra value is harmless and removal would require recreating the type.
    pass
