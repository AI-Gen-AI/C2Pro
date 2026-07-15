"""Add document versioning support

Revision ID: 20260406_0001
Revises: 20260405_0002
Create Date: 2026-04-06

TASK-BCK-023: Implement document update re-trigger flow
- Add version column for tracking document revisions
- Add file_hash column for detecting duplicate uploads
- Add index on file_hash for efficient lookup
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260406_0001'
down_revision = '20260405_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add version and file_hash columns to documents table."""
    # Add version column (default 1 for existing documents) — idempotent
    op.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1"
    )

    # Add file_hash column for duplicate detection — idempotent
    op.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64)"
    )

    # Add index on file_hash for efficient duplicate detection — idempotent
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_file_hash ON documents(file_hash)"
    )

    # Add composite index on (id, version) for version history queries — idempotent
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_id_version ON documents(id, version)"
    )


def downgrade() -> None:
    """Remove versioning columns and indexes."""
    # Drop indexes first
    op.drop_index('ix_documents_id_version', table_name='documents')
    op.drop_index('ix_documents_file_hash', table_name='documents')

    # Drop columns
    op.drop_column('documents', 'file_hash')
    op.drop_column('documents', 'version')
