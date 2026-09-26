"""P0c stable ProjectEvent total order index.

Revision ID: 20260913_0001
Revises: 20260907_0001
"""

from __future__ import annotations

from alembic import op

revision = "20260913_0001"
down_revision = "20260907_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make the `(occurred_at, event_id)` product ordering index-backed."""
    op.drop_index("ix_project_events_project_occurred", table_name="project_events")
    op.create_index(
        "ix_project_events_project_occurred",
        "project_events",
        ["project_id", "occurred_at", "event_id"],
    )


def downgrade() -> None:
    """Restore the pre-P0c index shape."""
    op.drop_index("ix_project_events_project_occurred", table_name="project_events")
    op.create_index(
        "ix_project_events_project_occurred", "project_events", ["project_id", "occurred_at"]
    )
