"""Add coherence_results table for dashboard queries.

Revision ID: 20260321_0002
Revises: 20260321_0001
Create Date: 2026-03-21

Suite ID: TS-E2E-FLW-DOC-001
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_0002"
down_revision: Union[str, None] = "20260321_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coherence_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            global_score INTEGER NOT NULL CHECK (global_score BETWEEN 0 AND 100),
            category_scores JSONB NOT NULL,
            category_details JSONB NOT NULL,
            alerts JSONB NOT NULL,
            is_gaming_detected BOOLEAN NOT NULL DEFAULT FALSE,
            gaming_violations TEXT[] NOT NULL DEFAULT '{}',
            penalty_points INTEGER NOT NULL DEFAULT 0,
            calculated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_coherence_results_project
        ON coherence_results(project_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_coherence_results_calculated_at
        ON coherence_results(calculated_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_coherence_results_project_calculated
        ON coherence_results(project_id, calculated_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS coherence_results CASCADE")
