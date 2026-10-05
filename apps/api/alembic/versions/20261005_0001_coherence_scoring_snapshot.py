"""B1: persist minimal Coherence scoring snapshot for exact HITL rescore.

Revision ID: 20261005_0001
Revises: 20261004_0002
Create Date: 2026-10-05

A human false-positive disposition changes scoring eligibility but must not rebuild
mathematics from the lossy Alerts projection or rerun non-deterministic detectors.
The nullable JSONB snapshot stores only the exact scoring inputs/context needed to
replay ScoringService against the same detected evidence basis.

Existing rows remain NULL and therefore fail closed for score-affecting review until
a fresh canonical evaluation seeds a snapshot.
"""

from __future__ import annotations

from alembic import op

revision = "20261005_0001"
down_revision = "20261004_0002"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261005000100_coherence_scoring_snapshot.sql"

ADD_SCORING_SNAPSHOT_SQL = """
ALTER TABLE public.coherence_results
    ADD COLUMN scoring_snapshot jsonb NULL
"""

UPGRADE_STATEMENTS: tuple[str, ...] = (ADD_SCORING_SNAPSHOT_SQL,)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE public.coherence_results DROP COLUMN scoring_snapshot",
)


def supabase_sql() -> str:
    """Render the Supabase CLI mirror from the same upgrade statements."""
    header = (
        "-- B1: exact Coherence scoring snapshot for disposition-aware rescoring.\n"
        "-- Mirror of apps/api/alembic/versions/20261005_0001_coherence_scoring_snapshot.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(
        statement.strip() + ";" for statement in UPGRADE_STATEMENTS
    ) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
