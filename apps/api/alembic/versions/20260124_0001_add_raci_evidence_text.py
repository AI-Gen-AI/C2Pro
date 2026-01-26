"""Add evidence_text to stakeholder_wbs_raci.

Revision ID: 20260124_0001
Revises: 20260104_0000
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260124_0001"
down_revision = "20260104_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stakeholder_wbs_raci", sa.Column("evidence_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stakeholder_wbs_raci", "evidence_text")
