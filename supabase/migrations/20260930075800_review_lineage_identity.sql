-- #758: the processing lineage a pending review may be resumed through.
-- Mirror of apps/api/alembic/versions/20260930_0758_review_lineage_identity.py.
-- Alembic remains authoritative.
--
-- Nullable with no backfill: NULL is the honest value for a review bound
-- before this identity existed, and such a row is exempt from the currency
-- comparison rather than refused by it. begin_generation stamps a NULL row
-- with the generation it belonged to as it bumps.

ALTER TABLE public.review_items ADD COLUMN lineage_generation bigint NULL;
ALTER TABLE public.review_items ADD COLUMN lineage_fencing_token bigint NULL;

CREATE INDEX IF NOT EXISTS ix_review_items_document_status
    ON public.review_items (document_id, current_status);
