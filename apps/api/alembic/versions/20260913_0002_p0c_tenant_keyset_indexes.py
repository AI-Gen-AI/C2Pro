"""P0c tenant-scoped timeline keyset indexes.

Revision ID: 20260913_0002
Revises: 20260913_0001
"""

from __future__ import annotations

from alembic import op

revision = "20260913_0002"
down_revision = "20260913_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_project_events_tenant_project_occurred_event",
        "project_events",
        ["tenant_id", "project_id", "occurred_at", "event_id"],
    )
    op.execute(
        "CREATE INDEX ix_project_events_tenant_project_source_revision_changed "
        "ON project_events (tenant_id, project_id, source_revision_id) "
        "WHERE event_type = 'revision.changed'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_project_events_tenant_project_source_revision_changed")
    op.drop_index("ix_project_events_tenant_project_occurred_event", table_name="project_events")
