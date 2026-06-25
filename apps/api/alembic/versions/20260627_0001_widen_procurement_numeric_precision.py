"""widen procurement numeric precision.

Revision ID: 20260627_0001
Revises: 20260626_0001
Create Date: 2026-06-27

Budget and BOM imports can exceed the prior NUMERIC(10, 2) ceiling. Widening
NUMERIC precision is non-destructive in PostgreSQL.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260627_0001"
down_revision: str | None = "20260626_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_project_bom_view() -> None:
    op.execute("DROP VIEW IF EXISTS v_project_bom")


def _create_project_bom_view() -> None:
    op.execute(
        """
        CREATE VIEW v_project_bom AS
        SELECT
            b.id,
            b.project_id,
            p.tenant_id,
            b.wbs_item_id,
            b.item_code,
            b.item_name,
            b.description,
            b.category,
            b.quantity,
            b.unit AS unit_of_measure,
            b.total_price AS total_cost,
            b.procurement_status,
            b.contract_clause_id AS source_clause_id,
            NULL::timestamp without time zone AS created_at
        FROM procurement_bom_items b
        JOIN projects p ON p.id = b.project_id
        WHERE b.project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )
    op.execute("ALTER VIEW v_project_bom SET (security_invoker = true)")


def upgrade() -> None:
    op.alter_column(
        "procurement_budget_items",
        "amount",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "procurement_wbs_items",
        "budget_allocated",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "procurement_wbs_items",
        "budget_spent",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
    _drop_project_bom_view()
    op.alter_column(
        "procurement_bom_items",
        "quantity",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(18, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "procurement_bom_items",
        "unit_price",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "procurement_bom_items",
        "total_price",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=True,
    )
    _create_project_bom_view()


def downgrade() -> None:
    _drop_project_bom_view()
    op.alter_column(
        "procurement_bom_items",
        "total_price",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "procurement_bom_items",
        "unit_price",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "procurement_bom_items",
        "quantity",
        existing_type=sa.Numeric(18, 4),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    _create_project_bom_view()
    op.alter_column(
        "procurement_wbs_items",
        "budget_spent",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "procurement_wbs_items",
        "budget_allocated",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "procurement_budget_items",
        "amount",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
