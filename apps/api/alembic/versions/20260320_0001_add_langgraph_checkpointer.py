"""Align LangGraph PostgreSQL checkpointer schema with runtime package.

Revision ID: 20260320_0001
Revises: 20260319_0008
Create Date: 2026-03-20

Task: B-3 - LangGraph Checkpointer (AUDIT-TASK-3.1)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260320_0001"
down_revision: str | None = "20260319_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create/repair LangGraph checkpoint tables with v3-compatible columns."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_migrations (
            v INTEGER PRIMARY KEY
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint JSONB NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_blobs (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL,
            version TEXT NOT NULL,
            type TEXT NOT NULL,
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            type TEXT,
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        )
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'ai_checkpoints'
            ) THEN
                INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)
                SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata
                FROM ai_checkpoints
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) DO NOTHING;
            END IF;
        END
        $$
        """
    )

    op.execute(
        """
        ALTER TABLE checkpoint_writes
        ADD COLUMN IF NOT EXISTS blob BYTEA
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'checkpoint_writes' AND column_name = 'value'
            ) THEN
                EXECUTE '
                    UPDATE checkpoint_writes
                    SET blob = COALESCE(blob, convert_to(COALESCE(value::text, ''null''), ''UTF8''))
                    WHERE blob IS NULL
                ';
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        ALTER TABLE checkpoint_writes
        ALTER COLUMN blob SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE checkpoint_writes
        DROP COLUMN IF EXISTS value
        """
    )
    op.execute(
        """
        ALTER TABLE checkpoint_writes
        ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT ''
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id)
        """
    )


def downgrade() -> None:
    """Rollback LangGraph checkpointing tables."""

    op.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")
