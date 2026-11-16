"""V4 S2 / WBS2.6 — share pending N4 liabilities with the legacy tenant cap.

Revision ID: 20261117_0001
Revises: 20261116_0002

Adds a reservation counter visible to legacy CostController. It is zeroed
only on initial schema adoption, not at period rollover. Refuse migration
over unaccounted historical N4 receipts: finance must reconcile first.
"""
from __future__ import annotations

from alembic import op

revision = "20261117_0001"
down_revision = "20261116_0002"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261117000100_n4_shared_tenant_reserved_budget.sql"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    """DO $do$ BEGIN
        PERFORM set_config('row_security', 'off', true);
        IF EXISTS (SELECT 1 FROM public.n4_usage_reservations LIMIT 1) THEN
            RAISE EXCEPTION 'Existing N4 receipts require reconciliation before shared budget adoption';
        END IF;
    END $do$""",
    "ALTER TABLE public.tenants ADD COLUMN ai_spend_reserved_usd "
    "numeric(16,6) NOT NULL DEFAULT 0",
    "ALTER TABLE public.tenants ADD CONSTRAINT ck_tenants_ai_reserved_nonnegative "
    "CHECK (ai_spend_reserved_usd >= 0)",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    """DO $do$ BEGIN
        PERFORM set_config('row_security', 'off', true);
        IF EXISTS (SELECT 1 FROM public.n4_usage_reservations LIMIT 1)
        OR EXISTS (SELECT 1 FROM public.tenants WHERE ai_spend_reserved_usd <> 0)
        THEN
            RAISE EXCEPTION 'Cannot downgrade shared budget with N4 receipts or reserved money';
        END IF;
    END $do$""",
    "ALTER TABLE public.tenants DROP CONSTRAINT ck_tenants_ai_reserved_nonnegative",
    "ALTER TABLE public.tenants DROP COLUMN ai_spend_reserved_usd",
)


def supabase_sql() -> str:
    return (
        "-- C2Pro V4 shared budget bridge; additive, backend-only.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261117_0001_n4_shared_tenant_reserved_budget.py\n"
        + "\n".join(stmt.strip() + ";\n" for stmt in UPGRADE_STATEMENTS)
    )


def upgrade() -> None:
    for sql in UPGRADE_STATEMENTS:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWNGRADE_STATEMENTS:
        op.execute(sql)
