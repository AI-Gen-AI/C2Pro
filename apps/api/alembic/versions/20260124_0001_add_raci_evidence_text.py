"""Add evidence_text to stakeholder_wbs_raci.

Revision ID: 20260124_0001
Revises: 20260104_0000
Create Date: 2026-01-24
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260124_0001"
down_revision = "20260104_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_name = "stakeholder_wbs_raci"
    column_name = "evidence_text"

    if not inspector.has_table(table_name):
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return

    op.add_column(table_name, sa.Column(column_name, sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_name = "stakeholder_wbs_raci"
    column_name = "evidence_text"

    if not inspector.has_table(table_name):
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name not in existing_columns:
        return

    op.drop_column(table_name, column_name)
