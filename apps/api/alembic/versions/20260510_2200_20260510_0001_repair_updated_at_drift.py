"""repair_updated_at_drift

Revision ID: 20260510_0001
Revises: 20260503_0001
Create Date: 2026-05-10 22:00:00.000000

PRODUCTION RECOVERY:
The column analyses.updated_at was declared in 20260315_0002 (line 153) but does not exist on
production (alembic_version was past that revision but the DDL never applied —
likely from a snapshot restore that pre-dated 20260315_0002 followed by a manual
version bump). CoherenceResultORM does NOT declare updated_at (only calculated_at),
so no recovery is needed for coherence_results.

This migration is fully idempotent (ADD COLUMN IF NOT EXISTS + IS NULL backfill)
and safe to run on environments where the column already exists.
"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260510_0001'
down_revision: str | None = '20260503_0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # analyses.updated_at — drift confirmed in production 2026-05-10.
    # Original declaration in 20260315_0002:153 uses sa.DateTime() which maps to
    # TIMESTAMP WITHOUT TIME ZONE in PostgreSQL. Matching that type exactly.
    op.execute("""
        ALTER TABLE analyses
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE
        NOT NULL DEFAULT now()
    """)
    # Backfill any rows where updated_at might be NULL (safety guard for
    # hypothetical race window between column add and DEFAULT application).
    op.execute(
        "UPDATE analyses SET updated_at = COALESCE(updated_at, created_at, now()) "
        "WHERE updated_at IS NULL"
    )

    # NOTE: coherence_results.updated_at is intentionally OMITTED.
    # CoherenceResultORM declares only calculated_at — there is no updated_at
    # column in the ORM, so adding it here would be dead schema.


def downgrade() -> None:
    op.execute("ALTER TABLE analyses DROP COLUMN IF EXISTS updated_at")
