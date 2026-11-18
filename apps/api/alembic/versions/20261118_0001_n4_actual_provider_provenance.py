"""N4 preserves reserved primary model and actual paid provider independently.

Revision ID: 20261118_0001
Revises: 20261117_0002
Additive; does not automatically activate provider fallback.
"""
from __future__ import annotations

from alembic import op

revision = "20261118_0001"
down_revision = "20261117_0002"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261118000100_n4_actual_provider_provenance.sql"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE public.n4_usage_reservations "
    "ADD COLUMN actual_model_name varchar(128) NULL",
    "ALTER TABLE public.n4_usage_reservations "
    "ADD COLUMN actual_provider varchar(24) NULL",
    "ALTER TABLE public.n4_usage_reservations ADD CONSTRAINT "
    "ck_n4_usage_actual_provider CHECK (actual_provider IS NULL OR "
    "actual_provider IN ('anthropic','openai','gemini'))",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    """DO $do$ BEGIN
    PERFORM set_config('row_security', 'off', true);
    IF EXISTS (
      SELECT 1 FROM public.n4_usage_reservations
       WHERE actual_model_name IS NOT NULL OR actual_provider IS NOT NULL
       LIMIT 1
    ) THEN
      RAISE EXCEPTION 'Cannot downgrade N4 actual model provenance with historical receipts';
    END IF;
    END $do$""",
    "ALTER TABLE public.n4_usage_reservations DROP CONSTRAINT ck_n4_usage_actual_provider",
    "ALTER TABLE public.n4_usage_reservations DROP COLUMN actual_provider",
    "ALTER TABLE public.n4_usage_reservations DROP COLUMN actual_model_name",
)


def supabase_sql() -> str:
    return (
        "-- C2Pro N4 direct-provider provenance; no data cleanup or backfill.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261118_0001_n4_actual_provider_provenance.py\n"
        + "\n".join(statement.strip() + ";\n" for statement in UPGRADE_STATEMENTS)
    )


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
