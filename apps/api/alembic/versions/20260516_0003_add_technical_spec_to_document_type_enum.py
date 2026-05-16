"""add technical_spec value to document_type enum.

Revision ID: 20260516_0003
Revises: 20260516_0002
Create Date: 2026-05-16

The Python DocumentType enum had TECHNICAL_SPEC as an alias for SPECIFICATION
(both mapped to 'specification'). Fixing the alias introduced a new distinct
value 'technical_spec' in the Python enum, but the PostgreSQL document_type
enum type was never updated. asyncpg validates enum values against the DB type
on every connection, so the mismatch broke ALL document uploads with a
ProgrammingError type cast error.

This migration adds 'technical_spec' to the PostgreSQL document_type enum.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260516_0003"
down_revision: str | None = "20260516_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction block on PG < 12.
    # Use autocommit_block for broad compatibility (PG 14+ on Supabase is fine
    # with it inside a transaction too, but this is the safe Alembic pattern).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'technical_spec'")


def downgrade() -> None:
    # Enum values cannot be removed in PostgreSQL without recreating the type.
    pass
