"""Shared budget reservation ledger for AI calls outside incremental N4.

Revision ID: 20261117_0002
Revises: 20261117_0001

Additive / non-destructive. Protected tenant-scoped ledger; it deliberately
does not change N4 windows, ProjectGraph, HITL or any AI graph routes.
"""
from __future__ import annotations

from alembic import op

revision = "20261117_0002"
down_revision = "20261117_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261117000200_legacy_ai_reservations.sql"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    """CREATE TABLE public.legacy_ai_usage_reservations (
        reservation_id uuid PRIMARY KEY,
        tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
        idempotency_key varchar(128) NOT NULL,
        call_source varchar(80) NOT NULL,
        reserved_usd numeric(16,6) NOT NULL,
        billed_usd numeric(16,6) NULL,
        status varchar(16) NOT NULL DEFAULT 'RESERVED',
        input_tokens bigint NULL,
        output_tokens bigint NULL,
        provider_model varchar(128) NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        settled_at timestamptz NULL,
        UNIQUE (tenant_id, idempotency_key),
        CONSTRAINT ck_legacy_ai_reserved_positive CHECK (reserved_usd > 0),
        CONSTRAINT ck_legacy_ai_billed_nonnegative CHECK
            (billed_usd IS NULL OR billed_usd >= 0),
        CONSTRAINT ck_legacy_ai_status CHECK
            (status IN ('RESERVED','UNKNOWN','SETTLED')),
        CONSTRAINT ck_legacy_ai_tokens CHECK
            ((input_tokens IS NULL OR input_tokens >= 0)
             AND (output_tokens IS NULL OR output_tokens >= 0)),
        CONSTRAINT ck_legacy_ai_settled CHECK
            (status <> 'SETTLED' OR billed_usd IS NOT NULL)
    )""",
    "CREATE INDEX idx_legacy_ai_usage_tenant_status "
    "ON public.legacy_ai_usage_reservations(tenant_id,status)",
    "ALTER TABLE public.legacy_ai_usage_reservations ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.legacy_ai_usage_reservations FORCE ROW LEVEL SECURITY",
    """CREATE POLICY legacy_ai_usage_tenant_read
       ON public.legacy_ai_usage_reservations FOR SELECT
       USING (tenant_id = nullif(current_setting('app.current_tenant', true),'')::uuid)""",
    """CREATE POLICY legacy_ai_usage_tenant_insert
       ON public.legacy_ai_usage_reservations FOR INSERT
       WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true),'')::uuid)""",
    """CREATE POLICY legacy_ai_usage_tenant_update
       ON public.legacy_ai_usage_reservations FOR UPDATE
       USING (tenant_id = nullif(current_setting('app.current_tenant', true),'')::uuid)
       WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true),'')::uuid)""",
    "REVOKE ALL ON public.legacy_ai_usage_reservations FROM PUBLIC",
    """DO $do$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
            EXECUTE 'REVOKE ALL ON public.legacy_ai_usage_reservations FROM anon';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
            EXECUTE 'REVOKE ALL ON public.legacy_ai_usage_reservations FROM authenticated';
        END IF;
    END $do$""",
    """CREATE FUNCTION public.legacy_ai_escrow_immutable_fields_20261117()
    RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER AS $fn$
    BEGIN
        IF (
            NEW.reservation_id, NEW.tenant_id, NEW.idempotency_key,
            NEW.call_source, NEW.reserved_usd, NEW.created_at
        ) IS DISTINCT FROM (
            OLD.reservation_id, OLD.tenant_id, OLD.idempotency_key,
            OLD.call_source, OLD.reserved_usd, OLD.created_at
        ) THEN
            RAISE EXCEPTION 'Legacy AI reservation identity/amount immutable';
        END IF;
        IF OLD.status = 'SETTLED' AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Settled AI usage is final';
        END IF;
        IF OLD.status = 'UNKNOWN' AND NEW.status = 'RESERVED' THEN
            RAISE EXCEPTION 'Unknown AI usage may not become fresh reservation';
        END IF;
        RETURN NEW;
    END $fn$""",
    "REVOKE ALL ON FUNCTION public.legacy_ai_escrow_immutable_fields_20261117() "
    "FROM PUBLIC",
    """CREATE TRIGGER trg_legacy_ai_escrow_immutable_20261117
       BEFORE UPDATE ON public.legacy_ai_usage_reservations
       FOR EACH ROW EXECUTE FUNCTION public.legacy_ai_escrow_immutable_fields_20261117()""",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    """DO $do$ BEGIN
        PERFORM set_config('row_security','off',true);
        IF EXISTS (SELECT 1 FROM public.legacy_ai_usage_reservations LIMIT 1)
        THEN RAISE EXCEPTION 'Cannot downgrade populated legacy AI budget ledger';
        END IF;
    END $do$""",
    "DROP TRIGGER trg_legacy_ai_escrow_immutable_20261117 "
    "ON public.legacy_ai_usage_reservations",
    "DROP TABLE public.legacy_ai_usage_reservations",
    "DROP FUNCTION public.legacy_ai_escrow_immutable_fields_20261117()",
)


def supabase_sql() -> str:
    return (
        "-- C2Pro V4 shared AI escrow, additive / default OFF.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261117_0002_legacy_ai_reservations.py\n"
        + "\n".join(statement.strip() + ";\n" for statement in UPGRADE_STATEMENTS)
    )


def upgrade() -> None:
    for sql in UPGRADE_STATEMENTS:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWNGRADE_STATEMENTS:
        op.execute(sql)
