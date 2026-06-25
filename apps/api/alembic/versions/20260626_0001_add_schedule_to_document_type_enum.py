"""add schedule value to document_type enum.

Revision ID: 20260626_0001
Revises: 20260624_0001
Create Date: 2026-06-26

The Python DocumentType enum includes SCHEDULE = "schedule", but the
PostgreSQL document_type enum was missing the matching value. asyncpg validates
enum values on INSERT, so schedule document uploads failed before persistence.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260626_0001"
down_revision: str | None = "20260624_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction block on PG < 12.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'schedule'")


def downgrade() -> None:
    # Enum values cannot be removed in PostgreSQL without recreating the type.
    pass
