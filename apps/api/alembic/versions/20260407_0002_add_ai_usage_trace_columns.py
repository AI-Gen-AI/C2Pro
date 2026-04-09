"""Add LangSmith trace columns to ai_usage_logs

Revision ID: 20260407_0002
Revises: 20260407_0001
Create Date: 2026-04-07 00:02:00.000000

TASK-IMPL-007: Fix AI Usage Log Schema Drift

Adds missing trace_id and trace_url columns required by AIUsageLogORM model.
These columns enable LangSmith integration for AI trace tracking.

Suite ID: TS-DB-MIG-AUD-004
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260407_0002"
down_revision: str = "20260407_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ai_usage_logs
        ADD COLUMN IF NOT EXISTS trace_id VARCHAR(255)
        """
    )
    op.execute(
        """
        ALTER TABLE ai_usage_logs
        ADD COLUMN IF NOT EXISTS trace_url TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_trace_id
        ON ai_usage_logs(trace_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_usage_logs_trace_id")
    op.execute("ALTER TABLE ai_usage_logs DROP COLUMN IF EXISTS trace_id")
    op.execute("ALTER TABLE ai_usage_logs DROP COLUMN IF EXISTS trace_url")
