-- C2Pro N4 direct-provider provenance; no data cleanup or backfill.
-- Mirror of apps/api/alembic/versions/20261118_0001_n4_actual_provider_provenance.py
ALTER TABLE public.n4_usage_reservations ADD COLUMN actual_model_name varchar(128) NULL;

ALTER TABLE public.n4_usage_reservations ADD COLUMN actual_provider varchar(24) NULL;

ALTER TABLE public.n4_usage_reservations ADD CONSTRAINT ck_n4_usage_actual_provider CHECK (actual_provider IS NULL OR actual_provider IN ('anthropic','openai','gemini'));
