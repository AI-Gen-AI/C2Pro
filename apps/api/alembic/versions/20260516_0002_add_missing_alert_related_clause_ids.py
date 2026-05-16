"""add missing alerts.related_clause_ids production repair column.

Revision ID: 20260516_0002
Revises: 20260516_0001
Create Date: 2026-05-16

Follow-up production drift repair for TASK-BCK-054.
The prior live repair revision had already been applied before Railway logs
proved that `alerts.related_clause_ids` was still absent in production, so this
must be a new forward migration rather than an edit to the applied revision.

Test Suite ID: TS-CI-BACKEND-GUARDS-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260516_0002"
down_revision: str | None = "20260516_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS related_clause_ids UUID[]")


def downgrade() -> None:
    # Recovery migration only; do not drop data-bearing columns automatically.
    pass
