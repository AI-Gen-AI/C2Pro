"""Add checkpoint tracking fields to review_items for LangGraph workflow resumption.

Part of TASK-BCK-024: Implement HITL workflow resume mechanism after approval.

Revision ID: 20260406_0002
Revises: 20260406_0001
"""

from __future__ import annotations

from alembic import op

revision: str = "20260406_0002"
down_revision: str | None = "20260406_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add checkpoint tracking fields for LangGraph workflow resumption."""
    # Add columns — all idempotent via ADD COLUMN IF NOT EXISTS
    op.execute("ALTER TABLE review_items ADD COLUMN IF NOT EXISTS checkpoint_id VARCHAR(255)")
    op.execute("ALTER TABLE review_items ADD COLUMN IF NOT EXISTS thread_id VARCHAR(255)")
    op.execute("ALTER TABLE review_items ADD COLUMN IF NOT EXISTS project_id UUID")
    op.execute("ALTER TABLE review_items ADD COLUMN IF NOT EXISTS document_id UUID")
    op.execute("ALTER TABLE review_items ADD COLUMN IF NOT EXISTS review_type VARCHAR(128)")
    op.execute("ALTER TABLE review_items ADD COLUMN IF NOT EXISTS review_decision TEXT")

    # Create indexes — idempotent
    op.execute("CREATE INDEX IF NOT EXISTS ix_review_items_checkpoint_id ON review_items(checkpoint_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_review_items_thread_id ON review_items(thread_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_review_items_project_status ON review_items(project_id, current_status)")

    # Create FK constraints — idempotent via DO block
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_review_items_project_id'
                  AND table_name = 'review_items'
            ) THEN
                ALTER TABLE review_items
                ADD CONSTRAINT fk_review_items_project_id
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
            END IF;
        END
        $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_review_items_document_id'
                  AND table_name = 'review_items'
            ) THEN
                ALTER TABLE review_items
                ADD CONSTRAINT fk_review_items_document_id
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Remove checkpoint tracking fields."""
    # Drop foreign keys first
    op.drop_constraint("fk_review_items_document_id", "review_items", type_="foreignkey")
    op.drop_constraint("fk_review_items_project_id", "review_items", type_="foreignkey")

    # Drop indexes
    op.drop_index("ix_review_items_project_status", table_name="review_items")
    op.drop_index("ix_review_items_thread_id", table_name="review_items")
    op.drop_index("ix_review_items_checkpoint_id", table_name="review_items")

    # Drop columns
    op.drop_column("review_items", "review_decision")
    op.drop_column("review_items", "review_type")
    op.drop_column("review_items", "document_id")
    op.drop_column("review_items", "project_id")
    op.drop_column("review_items", "thread_id")
    op.drop_column("review_items", "checkpoint_id")
