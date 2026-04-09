"""Add document versioning support

Revision ID: 20260406_0001
Revises: 20260405_0002
Create Date: 2026-04-06

TASK-BCK-023: Implement document update re-trigger flow
- Add version column for tracking document revisions
- Add file_hash column for detecting duplicate uploads
- Add index on file_hash for efficient lookup
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260406_0001'
down_revision = '20260405_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add version and file_hash columns to documents table."""
    # Add version column (default 1 for existing documents)
    op.add_column(
        'documents',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1')
    )

    # Add file_hash column for duplicate detection
    op.add_column(
        'documents',
        sa.Column('file_hash', sa.String(length=64), nullable=True)
    )

    # Add index on file_hash for efficient duplicate detection
    op.create_index(
        'ix_documents_file_hash',
        'documents',
        ['file_hash'],
        unique=False
    )

    # Add composite index on (id, version) for version history queries
    op.create_index(
        'ix_documents_id_version',
        'documents',
        ['id', 'version'],
        unique=False
    )


def downgrade() -> None:
    """Remove versioning columns and indexes."""
    # Drop indexes first
    op.drop_index('ix_documents_id_version', table_name='documents')
    op.drop_index('ix_documents_file_hash', table_name='documents')

    # Drop columns
    op.drop_column('documents', 'file_hash')
    op.drop_column('documents', 'version')
