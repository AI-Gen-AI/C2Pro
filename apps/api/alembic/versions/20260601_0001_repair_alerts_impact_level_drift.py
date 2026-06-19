"""repair alerts impact_level contract drift.

Revision ID: 20260601_0001
Revises: 20260530_0001
Create Date: 2026-06-01

Local Swagger verification showed ``GET /api/v1/alerts/projects/{project_id}``
failing because the current ORM selects ``alerts.impact_level`` while the live
database can still carry an older alerts table shape without that column.

Test Suite ID: TS-CI-BACKEND-GUARDS-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260601_0001"
down_revision: str | None = "20260530_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS impact_level VARCHAR(20)")


def downgrade() -> None:
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS impact_level")
