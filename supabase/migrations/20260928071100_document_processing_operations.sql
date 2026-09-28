-- #711 document-processing authority (attempts, fencing tokens, DB-clock leases).
-- Mirror of apps/api/alembic/versions/20260928_0711_document_processing_operations.py.
-- Alembic remains authoritative.

CREATE TABLE public.document_processing_operations (
    document_id uuid PRIMARY KEY
        REFERENCES public.documents(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    revision_id uuid NULL,
    generation bigint NOT NULL DEFAULT 1,
    stage varchar(16) NOT NULL,
    phase varchar(16) NOT NULL,
    attempt_id uuid NULL,
    owner_token uuid NULL,
    fencing_token bigint NOT NULL DEFAULT 0,
    lease_expires_at timestamp without time zone NULL,
    heartbeat_at timestamp without time zone NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    failure_count integer NOT NULL DEFAULT 0,
    outcome varchar(64) NULL,
    last_error text NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ck_document_processing_operations_stage
        CHECK (stage IN ('INGESTION','ANALYSIS')),
    CONSTRAINT ck_document_processing_operations_phase
        CHECK (phase IN ('PENDING','CLAIMED','RUNNING','COMPLETED','FAILED')),
    CONSTRAINT ck_document_processing_operations_fence
        CHECK (fencing_token >= 0)
);

CREATE INDEX ix_document_processing_operations_tenant_id
    ON public.document_processing_operations (tenant_id);

ALTER TABLE public.document_processing_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_processing_operations FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON public.document_processing_operations
    FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY tenant_isolation_insert ON public.document_processing_operations
    FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY tenant_isolation_update ON public.document_processing_operations
    FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY tenant_isolation_delete ON public.document_processing_operations
    FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
