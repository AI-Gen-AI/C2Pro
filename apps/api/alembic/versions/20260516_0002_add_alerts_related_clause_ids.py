"""add alerts.related_clause_ids column missing from drift repair.

Revision ID: 20260516_0002
Revises: 20260516_0001
Create Date: 2026-05-16

Production drift: 20260516_0001 repaired most missing columns on the alerts
table but omitted related_clause_ids (UUID[]). The ORM model and all downstream
code reference this column, causing every alert list query to crash with
UndefinedColumnError. This migration adds it idempotently.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260516_0002"
down_revision: str | None = "20260516_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS related_clause_ids UUID[]
        """
    )


def downgrade() -> None:
    pass
