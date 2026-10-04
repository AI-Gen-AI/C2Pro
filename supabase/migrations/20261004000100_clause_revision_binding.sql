-- Lane C / C3a: bind every clause row physically to the revision it was extracted from.
-- Mirror of apps/api/alembic/versions/20261004_0001_clause_revision_binding.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE public.document_revisions
    ADD CONSTRAINT uq_document_revisions_identity UNIQUE (revision_id, document_id, tenant_id);

ALTER TABLE public.clauses ADD COLUMN revision_id uuid NULL;

DO $$
DECLARE
    forced regclass[];
    rel regclass;
    report record;
BEGIN

    SELECT COALESCE(array_agg(c.oid::regclass), ARRAY[]::regclass[]) INTO forced
    FROM pg_class c
    WHERE c.relforcerowsecurity
      AND c.oid IN (SELECT to_regclass(name) FROM unnest(ARRAY['public.clauses', 'public.document_revisions']) AS name);
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s NO FORCE ROW LEVEL SECURITY', rel);
    END LOOP;

    UPDATE public.clauses c
       SET revision_id = r.revision_id
      FROM public.document_revisions r
     WHERE c.revision_id IS NULL
       AND jsonb_typeof(c.extracted_entities -> 'evidence_location') = 'object'
       -- AND does not order evaluation: the CASE keeps a malformed value from ever being cast.
       AND r.revision_id = CASE
            WHEN c.extracted_entities -> 'evidence_location' ->> 'revision_id' ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN (c.extracted_entities -> 'evidence_location' ->> 'revision_id')::uuid
           END
       AND r.document_id = c.document_id
       AND r.tenant_id = c.tenant_id;

    SELECT * INTO report FROM (
SELECT
    count(*)::bigint AS total,
    count(*) FILTER (WHERE outcome = 'bound')::bigint AS bound,
    count(*) FILTER (WHERE outcome <> 'bound')::bigint AS unbound,
    count(*) FILTER (WHERE outcome = 'malformed_source')::bigint AS malformed_source,
    count(*) FILTER (WHERE outcome = 'unknown_revision')::bigint AS unknown_revision,
    count(*) FILTER (WHERE outcome = 'cross_document_or_tenant')::bigint AS cross_document_or_tenant,
    count(*) FILTER (WHERE outcome = 'no_source')::bigint AS no_source
FROM (
    SELECT CASE
        WHEN c.revision_id IS NOT NULL THEN 'bound'
        WHEN c.extracted_entities -> 'evidence_location' IS NULL
          OR jsonb_typeof(c.extracted_entities -> 'evidence_location') = 'null'
          OR (jsonb_typeof(c.extracted_entities -> 'evidence_location') = 'object' AND c.extracted_entities -> 'evidence_location' ->> 'revision_id' IS NULL)
            THEN 'no_source'
        WHEN jsonb_typeof(c.extracted_entities -> 'evidence_location') <> 'object'
          OR NOT (c.extracted_entities -> 'evidence_location' ->> 'revision_id' ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
            THEN 'malformed_source'
        WHEN NOT EXISTS (
            SELECT 1 FROM public.document_revisions r
            WHERE r.revision_id = (c.extracted_entities -> 'evidence_location' ->> 'revision_id')::uuid
        ) THEN 'unknown_revision'
        ELSE 'cross_document_or_tenant'
    END AS outcome
    FROM public.clauses c
) AS classified
) AS counts;
    RAISE NOTICE 'C3a clause revision backfill: total=% bound=% unbound=% malformed_source=% '
                 'unknown_revision=% cross_document_or_tenant=% no_source=%',
        report.total, report.bound, report.unbound, report.malformed_source,
        report.unknown_revision, report.cross_document_or_tenant, report.no_source;

    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', rel);
    END LOOP;

END
$$;

ALTER TABLE public.clauses
    ADD CONSTRAINT fk_clauses_revision_identity
    FOREIGN KEY (revision_id, document_id, tenant_id)
    REFERENCES public.document_revisions (revision_id, document_id, tenant_id);

CREATE INDEX ix_clauses_tenant_document_revision
    ON public.clauses (tenant_id, document_id, revision_id);
