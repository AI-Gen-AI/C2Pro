"""V4 S2: retain unresolved source cross-references for a blocked N4 window.

Revision ID: 20261116_0002
Revises: 20261116_0001

This additive migration preserves the immutable first migration; a later
release can merge #1242 before this runner PR without rewriting a deployed
migration. No pilot activation or provider credentials.
"""
from __future__ import annotations

from alembic import op

revision = "20261116_0002"
down_revision = "20261116_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261116000200_n4_window_blocked_provenance.sql"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE public.n4_extraction_windows "
    "ADD COLUMN unresolved_refs jsonb NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE public.n4_extraction_windows "
    "ADD COLUMN blocked_reason varchar(80)",
    "ALTER TABLE public.n4_extraction_windows "
    "ADD CONSTRAINT ck_n4_windows_refs "
    "CHECK (jsonb_typeof(unresolved_refs) = 'array')",
    "ALTER TABLE public.n4_usage_reservations "
    "ADD COLUMN input_tokens bigint",
    "ALTER TABLE public.n4_usage_reservations "
    "ADD COLUMN output_tokens bigint",
    "ALTER TABLE public.n4_usage_reservations "
    "ADD COLUMN provider_request_id varchar(128)",
    "ALTER TABLE public.n4_usage_reservations "
    "ADD CONSTRAINT ck_n4_usage_token_nonnegative CHECK "
    "((input_tokens IS NULL OR input_tokens >= 0) "
    "AND (output_tokens IS NULL OR output_tokens >= 0))",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    """DO $do$ BEGIN
        PERFORM set_config('row_security', 'off', true);
        IF EXISTS (
            SELECT 1 FROM public.n4_usage_reservations
             WHERE input_tokens IS NOT NULL OR output_tokens IS NOT NULL
                OR provider_request_id IS NOT NULL LIMIT 1
        ) THEN
            RAISE EXCEPTION 'Cannot downgrade N4 provider usage provenance';
        END IF;
    END $do$""",
    """DO $do$ BEGIN
        PERFORM set_config('row_security', 'off', true);
        IF EXISTS (
            SELECT 1 FROM public.n4_extraction_windows
             WHERE blocked_reason IS NOT NULL
                OR unresolved_refs <> '[]'::jsonb
             LIMIT 1
        ) THEN
            RAISE EXCEPTION 'Cannot downgrade N4 blocked provenance with stored evidence';
        END IF;
    END $do$""",
    "ALTER TABLE public.n4_usage_reservations "
    "DROP CONSTRAINT ck_n4_usage_token_nonnegative",
    "ALTER TABLE public.n4_usage_reservations DROP COLUMN provider_request_id",
    "ALTER TABLE public.n4_usage_reservations DROP COLUMN output_tokens",
    "ALTER TABLE public.n4_usage_reservations DROP COLUMN input_tokens",
    "ALTER TABLE public.n4_extraction_windows DROP CONSTRAINT ck_n4_windows_refs",
    "ALTER TABLE public.n4_extraction_windows DROP COLUMN blocked_reason",
    "ALTER TABLE public.n4_extraction_windows DROP COLUMN unresolved_refs",
)


def supabase_sql() -> str:
    return (
        "-- C2Pro V4 WBS 2.x, blocked window provenance without rewriting 0001.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261116_0002_n4_window_blocked_provenance.py\n"
        + "\n".join(statement.strip() + ";\n" for statement in UPGRADE_STATEMENTS)
    )


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
