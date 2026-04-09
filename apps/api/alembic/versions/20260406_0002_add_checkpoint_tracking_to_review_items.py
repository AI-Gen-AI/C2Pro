"""Add checkpoint tracking fields to review_items for LangGraph workflow resumption.

Part of TASK-BCK-024: Implement HITL workflow resume mechanism after approval.

Revision ID: 20260406_0002
Revises: 20260406_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "20260406_0002"
down_revision: str | None = "20260406_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add checkpoint tracking fields for LangGraph workflow resumption."""
    # Add checkpoint_id for LangGraph checkpoint reference
    op.add_column(
        "review_items",
        sa.Column("checkpoint_id", sa.String(255), nullable=True),
    )

    # Add thread_id for LangGraph thread tracking
    op.add_column(
        "review_items",
        sa.Column("thread_id", sa.String(255), nullable=True),
    )

    # Add project_id FK for proper data relationships
    op.add_column(
        "review_items",
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
    )

    # Add document_id FK for document-related reviews
    op.add_column(
        "review_items",
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
    )

    # Add review_type for categorizing reviews
    op.add_column(
        "review_items",
        sa.Column("review_type", sa.String(128), nullable=True),
    )

    # Add review_decision for storing approval/rejection feedback
    op.add_column(
        "review_items",
        sa.Column("review_decision", sa.Text, nullable=True),
    )

    # Create index on checkpoint_id for fast lookups during resume
    op.create_index(
        "ix_review_items_checkpoint_id",
        "review_items",
        ["checkpoint_id"],
        unique=False,
    )

    # Create index on thread_id for workflow tracking
    op.create_index(
        "ix_review_items_thread_id",
        "review_items",
        ["thread_id"],
        unique=False,
    )

    # Create composite index on project_id and status for queue queries
    op.create_index(
        "ix_review_items_project_status",
        "review_items",
        ["project_id", "current_status"],
        unique=False,
    )

    # Create FK constraint to projects (if projects table exists)
    op.create_foreign_key(
        "fk_review_items_project_id",
        "review_items",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create FK constraint to documents (if documents table exists)
    op.create_foreign_key(
        "fk_review_items_document_id",
        "review_items",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )


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
