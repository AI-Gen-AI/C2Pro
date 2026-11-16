-- C2Pro V4 shared budget bridge; additive, backend-only.
-- Mirror of apps/api/alembic/versions/20261117_0001_n4_shared_tenant_reserved_budget.py
DO $do$ BEGIN
        PERFORM set_config('row_security', 'off', true);
        IF EXISTS (SELECT 1 FROM public.n4_usage_reservations LIMIT 1) THEN
            RAISE EXCEPTION 'Existing N4 receipts require reconciliation before shared budget adoption';
        END IF;
    END $do$;

ALTER TABLE public.tenants ADD COLUMN ai_spend_reserved_usd numeric(16,6) NOT NULL DEFAULT 0;

ALTER TABLE public.tenants ADD CONSTRAINT ck_tenants_ai_reserved_nonnegative CHECK (ai_spend_reserved_usd >= 0);
