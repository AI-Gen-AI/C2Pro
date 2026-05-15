"""repair alerts and stakeholders contract drift.

Revision ID: 20260516_0001
Revises: 20260510_0001
Create Date: 2026-05-16

Production drift recovery for TASK-BCK-051.
The live database reported the latest Alembic head while still retaining legacy
`alerts` and `stakeholders` table shapes that predate the current ORM contract.
This migration is intentionally idempotent so it is safe on environments where
the canonical columns already exist.

Test Suite ID: TS-CI-BACKEND-GUARDS-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260516_0001"
down_revision: str | None = "20260510_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'approvalstatus') THEN
                CREATE TYPE approvalstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CORRECTED');
            END IF;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS category VARCHAR(50)")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS recommendation TEXT")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS affected_entities JSONB DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS alert_metadata JSONB DEFAULT '{}'::jsonb")
    op.execute(
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS approval_status approvalstatus DEFAULT 'PENDING'"
    )
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS reviewed_by UUID")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS review_comment TEXT")

    op.execute("UPDATE alerts SET description = COALESCE(description, message, '')")
    op.execute("UPDATE alerts SET recommendation = COALESCE(recommendation, suggested_action)")
    op.execute(
        "UPDATE alerts SET affected_entities = COALESCE(affected_entities, '{}'::jsonb)"
    )
    op.execute("UPDATE alerts SET alert_metadata = COALESCE(alert_metadata, evidence_json, '{}'::jsonb)")
    op.execute("UPDATE alerts SET approval_status = COALESCE(approval_status, 'PENDING'::approvalstatus)")

    op.execute(
        "ALTER TABLE alerts ALTER COLUMN description SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE alerts ALTER COLUMN affected_entities SET DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE alerts ALTER COLUMN alert_metadata SET DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE alerts ALTER COLUMN approval_status SET DEFAULT 'PENDING'::approvalstatus"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_approval_status ON alerts(approval_status)"
    )

    op.execute(
        "ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS approval_status approvalstatus DEFAULT 'PENDING'"
    )
    op.execute("ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS reviewed_by UUID")
    op.execute("ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS review_comment TEXT")
    op.execute(
        "ALTER TABLE stakeholders ADD COLUMN IF NOT EXISTS stakeholder_metadata JSONB DEFAULT '{}'::jsonb"
    )
    op.execute(
        "UPDATE stakeholders SET stakeholder_metadata = COALESCE(stakeholder_metadata, metadata, '{}'::jsonb)"
    )
    op.execute(
        "UPDATE stakeholders SET approval_status = COALESCE(approval_status, 'PENDING'::approvalstatus)"
    )
    op.execute(
        "ALTER TABLE stakeholders ALTER COLUMN stakeholder_metadata SET DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE stakeholders ALTER COLUMN approval_status SET DEFAULT 'PENDING'::approvalstatus"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stakeholders_approval_status ON stakeholders(approval_status)"
    )


def downgrade() -> None:
    # Recovery migration only; do not drop data-bearing columns automatically.
    pass
