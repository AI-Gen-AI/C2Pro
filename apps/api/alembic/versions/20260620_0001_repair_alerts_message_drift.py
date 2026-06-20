"""repair alerts message drift.

Revision ID: 20260620_0001
Revises: 20260526_0001
Create Date: 2026-06-20

Production drift recovery for alerts.message. The Alert ORM and list-alerts
query path require this compatibility column, but earlier repair migrations
only copied legacy message values into description.

Test Suite ID: TS-HOTFIX-ALERTS-SCHEMA-DRIFT-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260620_0001"
down_revision: str | None = "20260526_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '30s'")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS message TEXT")
    op.execute(
        """
        UPDATE alerts
        SET message = COALESCE(message, description, title, '')
        WHERE message IS NULL
        """
    )
    op.execute("ALTER TABLE alerts ALTER COLUMN message SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS message")
