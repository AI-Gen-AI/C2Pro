-- C2Pro V4 WBS 2.x, blocked window provenance without rewriting 0001.
-- Mirror of apps/api/alembic/versions/20261116_0002_n4_window_blocked_provenance.py
ALTER TABLE public.n4_extraction_windows ADD COLUMN unresolved_refs jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.n4_extraction_windows ADD COLUMN blocked_reason varchar(80);

ALTER TABLE public.n4_extraction_windows ADD CONSTRAINT ck_n4_windows_refs CHECK (jsonb_typeof(unresolved_refs) = 'array');
