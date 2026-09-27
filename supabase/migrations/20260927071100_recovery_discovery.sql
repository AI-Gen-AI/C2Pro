-- #711 durable recovery discovery index.
-- Mirror of apps/api/alembic/versions/20260927_0711_recovery_discovery.py.
-- Alembic remains authoritative.

CREATE SCHEMA IF NOT EXISTS system_recovery;
REVOKE ALL ON SCHEMA system_recovery FROM PUBLIC;

CREATE TABLE system_recovery.document_work_index (
    document_id uuid PRIMARY KEY
        REFERENCES public.documents(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    upload_status text NULL,
    updated_at timestamp without time zone NOT NULL
);

CREATE INDEX ix_document_work_index_recovery_scan
    ON system_recovery.document_work_index
        (upload_status, updated_at, document_id);

REVOKE ALL ON TABLE system_recovery.document_work_index FROM PUBLIC;

CREATE OR REPLACE FUNCTION system_recovery.sync_document_work_index()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, system_recovery
AS $recovery$
DECLARE
    row_json jsonb := to_jsonb(NEW);
    row_updated_at timestamp without time zone;
BEGIN
    BEGIN
        row_updated_at := NULLIF(row_json ->> 'updated_at', '')::timestamp;
    EXCEPTION WHEN invalid_datetime_format THEN
        row_updated_at := NULL;
    END;

    INSERT INTO system_recovery.document_work_index (
        document_id,
        tenant_id,
        upload_status,
        updated_at
    )
    VALUES (
        NEW.id,
        NEW.tenant_id,
        row_json ->> 'upload_status',
        COALESCE(row_updated_at, clock_timestamp() AT TIME ZONE 'UTC')
    )
    ON CONFLICT (document_id) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id,
            upload_status = EXCLUDED.upload_status,
            updated_at = EXCLUDED.updated_at;
    RETURN NEW;
END
$recovery$;

REVOKE ALL ON FUNCTION system_recovery.sync_document_work_index() FROM PUBLIC;

CREATE TRIGGER trg_documents_recovery_index
AFTER INSERT OR UPDATE ON public.documents
FOR EACH ROW
EXECUTE FUNCTION system_recovery.sync_document_work_index();

DO $backfill$
DECLARE
    has_upload_status boolean;
    force_rls boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = 'public.documents'::regclass
           AND attname = 'upload_status'
           AND NOT attisdropped
    ) INTO has_upload_status;

    IF NOT has_upload_status THEN
        RETURN;
    END IF;

    SELECT relforcerowsecurity
      INTO force_rls
      FROM pg_class
     WHERE oid = 'public.documents'::regclass;

    LOCK TABLE public.documents IN ACCESS EXCLUSIVE MODE;

    IF force_rls THEN
        EXECUTE 'ALTER TABLE public.documents NO FORCE ROW LEVEL SECURITY';
    END IF;

    BEGIN
        EXECUTE
            'INSERT INTO system_recovery.document_work_index '
            '(document_id, tenant_id, upload_status, updated_at) '
            'SELECT id, tenant_id, upload_status::text, updated_at '
            'FROM public.documents '
            'ON CONFLICT (document_id) DO UPDATE '
            'SET tenant_id = EXCLUDED.tenant_id, '
            'upload_status = EXCLUDED.upload_status, '
            'updated_at = EXCLUDED.updated_at';
    EXCEPTION WHEN OTHERS THEN
        IF force_rls THEN
            EXECUTE 'ALTER TABLE public.documents FORCE ROW LEVEL SECURITY';
        END IF;
        RAISE;
    END;

    IF force_rls THEN
        EXECUTE 'ALTER TABLE public.documents FORCE ROW LEVEL SECURITY';
    END IF;
END
$backfill$;
