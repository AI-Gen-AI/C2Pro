"""Add PARSED_PENDING_ANALYSIS and ANALYZED to document_status enum

Revision ID: 20260405_0001
Revises: 20260403_0003
Create Date: 2026-04-05 20:11:00

Part of TASK-BCK-022: Wire TriggerDocumentAnalysisUseCase to Celery ingestion completion
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260405_0001'
down_revision = '20260403_0003'
branch_labels = None
depends_on = None


def upgrade():
    """Add new document_status enum values for analysis flow."""

    # PostgreSQL requires ALTER TYPE ADD VALUE to add new enum values
    # These values support the decoupled ingestion→analysis flow
    op.execute("""
        ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'parsed_pending_analysis';
    """)

    op.execute("""
        ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'analyzed';
    """)


def downgrade():
    """Remove analysis status values.

    WARNING: PostgreSQL does NOT support removing enum values directly.
    This downgrade requires recreating the enum type, which is risky in production.

    If any documents use these statuses, this migration will fail.
    Manual intervention required:
    1. UPDATE documents SET upload_status = 'parsed' WHERE upload_status IN ('parsed_pending_analysis', 'analyzed');
    2. Then run downgrade.
    """

    # Step 1: Create new enum without the analysis values
    op.execute("""
        CREATE TYPE document_status_old AS ENUM (
            'uploaded',
            'queued',
            'processing',
            'parsed',
            'error'
        );
    """)

    # Step 2: Update table to use old enum (will fail if analysis statuses are in use)
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN upload_status TYPE document_status_old
        USING upload_status::text::document_status_old;
    """)

    # Step 3: Drop new enum
    op.execute("DROP TYPE document_status;")

    # Step 4: Rename old enum to original name
    op.execute("ALTER TYPE document_status_old RENAME TO document_status;")
