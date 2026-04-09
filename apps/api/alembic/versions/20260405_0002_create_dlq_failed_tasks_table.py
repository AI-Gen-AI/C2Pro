"""Create dlq_failed_tasks table for dead letter queue

Revision ID: 20260405_0002
Revises: 20260405_0001
Create Date: 2026-04-05 20:20:00

Part of TASK-BCK-022: Wire TriggerDocumentAnalysisUseCase to Celery ingestion completion
Implements Dead Letter Queue for failed analysis triggers with retry logic.
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260405_0002'
down_revision = '20260405_0001'
branch_labels = None
depends_on = None


def upgrade():
    """Create dlq_failed_tasks table with RLS support."""

    # Create DLQ status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dlq_status') THEN
                CREATE TYPE dlq_status AS ENUM ('pending', 'retrying', 'exhausted');
            END IF;
        END
        $$;
    """)

    # Create dlq_failed_tasks table
    op.create_table(
        'dlq_failed_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False, comment='Tenant isolation'),
        sa.Column('task_type', sa.String(100), nullable=False, comment='Type of task that failed (e.g., document_analysis)'),
        sa.Column('document_id', UUID(as_uuid=True), nullable=True, comment='Related document ID if applicable'),
        sa.Column('payload_json', JSONB, nullable=False, comment='Original task payload for retry'),
        sa.Column('error_message', sa.Text, nullable=False, comment='Error message from failure'),
        sa.Column('error_traceback', sa.Text, nullable=True, comment='Full error traceback for debugging'),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0', comment='Number of retry attempts'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='3', comment='Maximum retry attempts before exhaustion'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('next_retry_at', TIMESTAMP(timezone=True), nullable=True, comment='Scheduled time for next retry (exponential backoff)'),
        comment='Dead Letter Queue for failed async tasks with retry mechanism'
    )

    # Add foreign key to documents (nullable for non-document tasks)
    op.create_foreign_key(
        'fk_dlq_failed_tasks_document',
        'dlq_failed_tasks',
        'documents',
        ['document_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add indexes for efficient queries
    op.create_index(
        'idx_dlq_failed_tasks_tenant_status',
        'dlq_failed_tasks',
        ['tenant_id', 'status']
    )

    op.create_index(
        'idx_dlq_failed_tasks_next_retry',
        'dlq_failed_tasks',
        ['next_retry_at'],
        postgresql_where=sa.text("status = 'pending' OR status = 'retrying'")
    )

    op.create_index(
        'idx_dlq_failed_tasks_document_id',
        'dlq_failed_tasks',
        ['document_id']
    )

    # Enable RLS on dlq_failed_tasks
    op.execute("""
        ALTER TABLE dlq_failed_tasks ENABLE ROW LEVEL SECURITY;
    """)

    # Create RLS policy for tenant isolation
    op.execute("""
        CREATE POLICY dlq_tenant_isolation
        ON dlq_failed_tasks
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);
    """)

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_dlq_failed_tasks_updated_at
        BEFORE UPDATE ON dlq_failed_tasks
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    """Drop dlq_failed_tasks table and related objects."""

    op.execute("DROP TRIGGER IF EXISTS update_dlq_failed_tasks_updated_at ON dlq_failed_tasks;")
    op.execute("DROP POLICY IF EXISTS dlq_tenant_isolation ON dlq_failed_tasks;")

    op.drop_index('idx_dlq_failed_tasks_document_id', table_name='dlq_failed_tasks')
    op.drop_index('idx_dlq_failed_tasks_next_retry', table_name='dlq_failed_tasks')
    op.drop_index('idx_dlq_failed_tasks_tenant_status', table_name='dlq_failed_tasks')

    op.drop_constraint('fk_dlq_failed_tasks_document', 'dlq_failed_tasks', type_='foreignkey')
    op.drop_table('dlq_failed_tasks')

    op.execute("DROP TYPE IF EXISTS dlq_status;")
