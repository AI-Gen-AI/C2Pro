"""Add score versioning fields to coherence_results.

Revision ID: 20260425_0001
Revises: 20260421_0001
Create Date: 2026-04-25 00:01:00.000000

Suite ID: TS-INT-DB-COH-001
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260425_0001"
down_revision: str = "20260421_0001"
branch_labels = None
depends_on = None

_ENUM_NAME = "coherence_score_version"


def upgrade() -> None:
    """Add immutable audit-trail fields for score-version transitions."""
    op.execute("SET LOCAL lock_timeout = '30s';")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{_ENUM_NAME}') THEN
                CREATE TYPE {_ENUM_NAME} AS ENUM ('v0_flag_based', 'v1_exponential_decay');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        f"""
        ALTER TABLE coherence_results
        ADD COLUMN IF NOT EXISTS score_version {_ENUM_NAME}
            NOT NULL DEFAULT 'v0_flag_based'
        """
    )
    op.execute(
        """
        ALTER TABLE coherence_results
        ADD COLUMN IF NOT EXISTS score_reason TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE coherence_results
        ADD COLUMN IF NOT EXISTS score_missing_dimensions JSONB
        """
    )


def downgrade() -> None:
    """Remove score-version audit fields."""
    op.execute("SET LOCAL lock_timeout = '30s';")
    op.execute("ALTER TABLE coherence_results DROP COLUMN IF EXISTS score_missing_dimensions")
    op.execute("ALTER TABLE coherence_results DROP COLUMN IF EXISTS score_reason")
    op.execute("ALTER TABLE coherence_results DROP COLUMN IF EXISTS score_version")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM_NAME}")
