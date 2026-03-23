"""Fix WBS code uniqueness scope per project.

Revision ID: 20260321_0001
Revises: 20260320_0001
Create Date: 2026-03-21

Suite ID: TS-INT-DB-WBS-001
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260321_0001"
down_revision: Union[str, None] = "20260320_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Scope WBS code uniqueness to project and enforce parent relation per project."""

    op.execute("ALTER TABLE procurement_wbs_items DROP CONSTRAINT IF EXISTS fk_wbs_parent")
    op.execute("ALTER TABLE procurement_wbs_items DROP CONSTRAINT IF EXISTS procurement_wbs_items_code_key")

    op.execute(
        """
        ALTER TABLE procurement_wbs_items
        ADD CONSTRAINT uq_procurement_wbs_project_code UNIQUE (project_id, code)
        """
    )

    op.execute(
        """
        ALTER TABLE procurement_wbs_items
        ADD CONSTRAINT fk_wbs_parent_per_project
        FOREIGN KEY (project_id, parent_code)
        REFERENCES procurement_wbs_items(project_id, code)
        ON DELETE CASCADE
        DEFERRABLE INITIALLY DEFERRED
        """
    )


def downgrade() -> None:
    """Rollback WBS uniqueness/project-scoped parent relation."""

    op.execute("ALTER TABLE procurement_wbs_items DROP CONSTRAINT IF EXISTS fk_wbs_parent_per_project")
    op.execute("ALTER TABLE procurement_wbs_items DROP CONSTRAINT IF EXISTS uq_procurement_wbs_project_code")

    op.execute(
        """
        ALTER TABLE procurement_wbs_items
        ADD CONSTRAINT procurement_wbs_items_code_key UNIQUE (code)
        """
    )

    op.execute(
        """
        ALTER TABLE procurement_wbs_items
        ADD CONSTRAINT fk_wbs_parent
        FOREIGN KEY (parent_code)
        REFERENCES procurement_wbs_items(code)
        ON DELETE SET NULL
        """
    )
