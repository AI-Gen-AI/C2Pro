"""Add audit chain fields to audit_logs

Revision ID: 20260407_0001
Revises: 20260406_0005
Create Date: 2026-04-07 00:01:00.000000

TASK-IMPL-002: Fix AuditLog Traceability Failure

This migration adds missing columns required by SQLAlchemyAuditRepository:
- actor_id: UUID referencing users (renamed from user_id conceptually)
- event_hash: SHA256 hash for audit chain integrity
- previous_hash: Previous event hash for chain linking

Also adds column aliases for repository compatibility:
- timestamp: Alias for created_at
- metadata_json: Alias for changes

Suite ID: TS-DB-MIG-AUD-003
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260407_0001"
down_revision: str = "20260406_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add actor_id column (UUID referencing users)
    op.execute(
        """
        ALTER TABLE audit_logs
        ADD COLUMN IF NOT EXISTS actor_id UUID REFERENCES users(id) ON DELETE SET NULL
        """
    )

    # Add event_hash column for audit chain integrity
    op.execute(
        """
        ALTER TABLE audit_logs
        ADD COLUMN IF NOT EXISTS event_hash VARCHAR(64)
        """
    )

    # Add previous_hash column for audit chain linking
    op.execute(
        """
        ALTER TABLE audit_logs
        ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64)
        """
    )

    # Add timestamp column as alias for created_at (for repository compatibility)
    op.execute(
        """
        ALTER TABLE audit_logs
        ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ DEFAULT NOW()
        """
    )

    # Backfill timestamp from created_at for existing records
    op.execute(
        """
        UPDATE audit_logs
        SET timestamp = created_at
        WHERE timestamp IS NULL
        """
    )

    # Add metadata_json column as alias for changes (for repository compatibility)
    op.execute(
        """
        ALTER TABLE audit_logs
        ADD COLUMN IF NOT EXISTS metadata_json JSONB DEFAULT '{}'
        """
    )

    # Backfill metadata_json from changes for existing records
    op.execute(
        """
        UPDATE audit_logs
        SET metadata_json = changes
        WHERE metadata_json IS NULL OR metadata_json = '{}'::jsonb
        """
    )

    # Create indexes for new columns
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs(actor_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_event_hash ON audit_logs(event_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_previous_hash ON audit_logs(previous_hash)
        """
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_actor")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_event_hash")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_previous_hash")

    # Drop columns
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS actor_id")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS event_hash")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS previous_hash")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS timestamp")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS metadata_json")
