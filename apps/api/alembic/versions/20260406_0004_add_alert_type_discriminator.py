"""add alert_type discriminator

Revision ID: 20260406_0004
Revises: 20260406_0003
Create Date: 2026-04-06

TASK-BCK-026: Unify AlertGenerator with pipeline save_to_db_node.
Adds alert_type discriminator (risk | coherence | budget | wbs) to alerts table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260406_0004"
down_revision: str | None = "20260406_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add alert_type discriminator to alerts table.

    Changes:
    1. Create alert_type enum type
    2. Add alert_type column with default='risk'
    3. Create index on alert_type
    4. Backfill existing alerts based on rule_id presence
    """
    # Create alert_type enum (idempotent — safe to re-run)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alerttype') THEN
                CREATE TYPE alerttype AS ENUM ('risk', 'coherence', 'budget', 'wbs');
            END IF;
        END
        $$;
    """)

    # Add alert_type column with default='risk' for backward compatibility (idempotent)
    op.execute("""
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS alert_type alerttype NOT NULL DEFAULT 'risk'
    """)

    # Backfill existing alerts:
    # - If rule_id is not null → alert_type='coherence' (from coherence rules)
    # - Otherwise → alert_type='risk' (from risk extraction)
    op.execute("""
        UPDATE alerts
        SET alert_type = 'coherence'
        WHERE rule_id IS NOT NULL AND alert_type = 'risk'
    """)

    # Create index on alert_type for efficient filtering (idempotent)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_alerts_alert_type ON alerts(alert_type)
    """)


def downgrade() -> None:
    """
    Remove alert_type discriminator.

    This will drop the alert_type column and enum type.
    WARNING: This will lose alert type information!
    """
    # Drop index
    op.drop_index("ix_alerts_alert_type", table_name="alerts")

    # Drop column
    op.drop_column("alerts", "alert_type")

    # Drop enum type
    op.execute("DROP TYPE alerttype")
