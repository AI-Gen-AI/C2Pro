-- C2Pro V4 WBS 2.x, blocked window provenance without rewriting 0001.
-- Mirror of apps/api/alembic/versions/20261116_0002_n4_window_blocked_provenance.py
ALTER TABLE public.n4_extraction_windows ADD COLUMN unresolved_refs jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.n4_extraction_windows ADD COLUMN blocked_reason varchar(80);

ALTER TABLE public.n4_extraction_windows ADD CONSTRAINT ck_n4_windows_refs CHECK (jsonb_typeof(unresolved_refs) = 'array');

ALTER TABLE public.n4_usage_reservations ADD COLUMN input_tokens bigint;

ALTER TABLE public.n4_usage_reservations ADD COLUMN output_tokens bigint;

ALTER TABLE public.n4_usage_reservations ADD COLUMN provider_request_id varchar(128);

ALTER TABLE public.n4_usage_reservations ADD CONSTRAINT ck_n4_usage_token_nonnegative CHECK ((input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0));
