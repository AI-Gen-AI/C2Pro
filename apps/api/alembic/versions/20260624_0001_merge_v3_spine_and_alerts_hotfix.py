"""merge v3 spine and alerts hotfix heads.

Revision ID: 20260624_0001
Revises: 20260614_0004, 20260620_0001
Create Date: 2026-06-24

Unifies the two divergent Alembic heads created when the v3 spine work
(#158, head 20260614_0004) and the alerts/analysis honesty hotfix
(#162, head 20260620_0001) were both merged into main. Both heads share
the common ancestor 20260526_0001. No schema changes -- DAG join only so
that ``alembic upgrade head`` resolves to a single head again (start.sh
runs ``alembic upgrade head`` on container boot).

Test Suite ID: TS-HOTFIX-ALEMBIC-HEAD-MERGE-001.
"""

from collections.abc import Sequence

revision: str = "20260624_0001"
down_revision: tuple[str, str] = ("20260614_0004", "20260620_0001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Pure DAG join -- no schema changes."""


def downgrade() -> None:
    """Pure DAG join -- no schema changes."""
