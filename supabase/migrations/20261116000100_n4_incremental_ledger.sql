-- C2Pro V4 WBS2.2/2.5/2.6 incremental N4 ledger; additive, no runtime activation.
-- Mirror of apps/api/alembic/versions/20261116_0001_n4_incremental_ledger.py.

CREATE TABLE public.n4_extraction_runs (
    run_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    document_revision_id uuid NOT NULL,
    source_sha256 char(64) NOT NULL,
    config_sha256 char(64) NOT NULL,
    generation bigint NOT NULL,
    fencing_token bigint NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'PREPARING',
    total_windows integer NOT NULL,
    budget_cap_usd numeric(16,6) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_n4_runs_tenant_run UNIQUE (tenant_id, run_id),
    CONSTRAINT uq_n4_runs_identity UNIQUE
        (tenant_id, document_revision_id, source_sha256, config_sha256, generation),
    CONSTRAINT fk_n4_runs_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE NO ACTION,
    CONSTRAINT fk_n4_runs_revision FOREIGN KEY
        (document_revision_id, document_id, project_id, tenant_id)
        REFERENCES public.document_revisions
        (revision_id, document_id, project_id, tenant_id) ON DELETE NO ACTION,
    CONSTRAINT ck_n4_runs_sha CHECK
        (source_sha256 ~ '^[a-f0-9]{64}$' AND config_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT ck_n4_runs_generation CHECK (generation > 0 AND fencing_token >= 0),
    CONSTRAINT ck_n4_runs_windows CHECK (total_windows > 0),
    CONSTRAINT ck_n4_runs_budget CHECK (budget_cap_usd > 0),
    CONSTRAINT ck_n4_runs_status CHECK (status IN
        ('PREPARING','RUNNING','PARTIAL','BLOCKED','FAILED','COMPLETE'))
);

CREATE TABLE public.n4_extraction_windows (
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    ordinal integer NOT NULL,
    core_start integer NOT NULL,
    core_end integer NOT NULL,
    context_start integer NOT NULL,
    context_end integer NOT NULL,
    context_sha256 char(64) NOT NULL,
    findings_sha256 char(64) NULL,
    status varchar(16) NOT NULL DEFAULT 'PENDING',
    committed_at timestamptz NULL,
    PRIMARY KEY (tenant_id, run_id, ordinal),
    CONSTRAINT fk_n4_windows_run FOREIGN KEY (tenant_id, run_id)
        REFERENCES public.n4_extraction_runs (tenant_id, run_id) ON DELETE CASCADE,
    CONSTRAINT ck_n4_windows_bounds CHECK
        (ordinal >= 0 AND context_start >= 0 AND core_start >= context_start
         AND core_end > core_start AND context_end >= core_end),
    CONSTRAINT ck_n4_windows_sha CHECK
        (context_sha256 ~ '^[a-f0-9]{64}$'
         AND (findings_sha256 IS NULL OR findings_sha256 ~ '^[a-f0-9]{64}$')),
    CONSTRAINT ck_n4_windows_result CHECK
        (status <> 'EXAMINED' OR findings_sha256 IS NOT NULL),
    CONSTRAINT ck_n4_windows_status CHECK (status IN
        ('PENDING','CLAIMED','EXAMINED','FAILED','BLOCKED'))
);

CREATE TABLE public.n4_candidate_findings (
    finding_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    window_ordinal integer NOT NULL,
    finding_key char(64) NOT NULL,
    source_refs jsonb NOT NULL,
    claim jsonb NOT NULL,
    candidate_state varchar(16) NOT NULL DEFAULT 'PROPOSED',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_n4_finding_tenant_id UNIQUE (tenant_id, finding_id),
    CONSTRAINT uq_n4_finding_dedupe UNIQUE (tenant_id, run_id, finding_key),
    CONSTRAINT fk_n4_findings_window FOREIGN KEY
        (tenant_id, run_id, window_ordinal)
        REFERENCES public.n4_extraction_windows (tenant_id, run_id, ordinal)
        ON DELETE CASCADE,
    CONSTRAINT ck_n4_finding_key CHECK (finding_key ~ '^[a-f0-9]{64}$'),
    CONSTRAINT ck_n4_finding_source CHECK (jsonb_typeof(source_refs) = 'array'),
    CONSTRAINT ck_n4_finding_claim CHECK (jsonb_typeof(claim) = 'object'),
    CONSTRAINT ck_n4_candidate_proposed CHECK (candidate_state = 'PROPOSED')
);

CREATE TABLE public.n4_budget_buckets (
    tenant_id uuid NOT NULL,
    scope_kind varchar(16) NOT NULL,
    scope_id uuid NOT NULL,
    period_key varchar(16) NOT NULL,
    cap_usd numeric(16,6) NOT NULL,
    reserved_usd numeric(16,6) NOT NULL DEFAULT 0,
    spent_usd numeric(16,6) NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, scope_kind, scope_id, period_key),
    CONSTRAINT ck_n4_budget_scope CHECK
        (scope_kind IN ('TENANT','PROJECT','DOCUMENT','RUN')),
    CONSTRAINT ck_n4_budget_period CHECK (length(btrim(period_key)) > 0),
    CONSTRAINT ck_n4_budget_nonnegative CHECK
        (cap_usd > 0 AND reserved_usd >= 0 AND spent_usd >= 0)
);

CREATE TABLE public.n4_usage_reservations (
    reservation_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    window_ordinal integer NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    bucket_scopes jsonb NOT NULL,
    reserved_usd numeric(16,6) NOT NULL,
    spent_usd numeric(16,6) NULL,
    status varchar(16) NOT NULL DEFAULT 'RESERVED',
    model_name varchar(120) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    settled_at timestamptz NULL,
    CONSTRAINT uq_n4_usage_tenant_id UNIQUE (tenant_id, reservation_id),
    CONSTRAINT uq_n4_usage_idempotency UNIQUE (tenant_id, run_id, idempotency_key),
    CONSTRAINT fk_n4_usage_window FOREIGN KEY
        (tenant_id, run_id, window_ordinal)
        REFERENCES public.n4_extraction_windows (tenant_id, run_id, ordinal)
        ON DELETE RESTRICT,
    CONSTRAINT ck_n4_usage_status CHECK
        (status IN ('RESERVED','SETTLED','UNKNOWN','CANCELED')),
    CONSTRAINT ck_n4_usage_amount CHECK
        (reserved_usd > 0 AND (spent_usd IS NULL OR spent_usd >= 0)),
    CONSTRAINT ck_n4_usage_scopes CHECK
        (jsonb_typeof(bucket_scopes) = 'array'
         AND jsonb_array_length(bucket_scopes) = 4),
    CONSTRAINT ck_n4_usage_settled CHECK
        ((status = 'SETTLED') = (spent_usd IS NOT NULL))
);

CREATE INDEX ix_n4_runs_project ON public.n4_extraction_runs (tenant_id, project_id, document_id, created_at DESC);

CREATE INDEX ix_n4_windows_status ON public.n4_extraction_windows (tenant_id, run_id, status);

CREATE INDEX ix_n4_findings_run ON public.n4_candidate_findings (tenant_id, run_id, window_ordinal);

CREATE INDEX ix_n4_usage_run_status ON public.n4_usage_reservations (tenant_id, run_id, status);

ALTER TABLE public.n4_extraction_runs ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.n4_extraction_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY n4_n4_extraction_runs_select ON public.n4_extraction_runs FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_extraction_runs_insert ON public.n4_extraction_runs FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_extraction_runs_update ON public.n4_extraction_runs FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

REVOKE ALL ON TABLE public.n4_extraction_runs FROM PUBLIC;

ALTER TABLE public.n4_extraction_windows ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.n4_extraction_windows FORCE ROW LEVEL SECURITY;

CREATE POLICY n4_n4_extraction_windows_select ON public.n4_extraction_windows FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_extraction_windows_insert ON public.n4_extraction_windows FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_extraction_windows_update ON public.n4_extraction_windows FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

REVOKE ALL ON TABLE public.n4_extraction_windows FROM PUBLIC;

ALTER TABLE public.n4_candidate_findings ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.n4_candidate_findings FORCE ROW LEVEL SECURITY;

CREATE POLICY n4_n4_candidate_findings_select ON public.n4_candidate_findings FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_candidate_findings_insert ON public.n4_candidate_findings FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

REVOKE ALL ON TABLE public.n4_candidate_findings FROM PUBLIC;

ALTER TABLE public.n4_budget_buckets ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.n4_budget_buckets FORCE ROW LEVEL SECURITY;

CREATE POLICY n4_n4_budget_buckets_select ON public.n4_budget_buckets FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_budget_buckets_insert ON public.n4_budget_buckets FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_budget_buckets_update ON public.n4_budget_buckets FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

REVOKE ALL ON TABLE public.n4_budget_buckets FROM PUBLIC;

ALTER TABLE public.n4_usage_reservations ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.n4_usage_reservations FORCE ROW LEVEL SECURITY;

CREATE POLICY n4_n4_usage_reservations_select ON public.n4_usage_reservations FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_usage_reservations_insert ON public.n4_usage_reservations FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY n4_n4_usage_reservations_update ON public.n4_usage_reservations FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

REVOKE ALL ON TABLE public.n4_usage_reservations FROM PUBLIC;

DO $do$
DECLARE r text; t text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            FOREACH t IN ARRAY ARRAY[
                'n4_extraction_runs','n4_extraction_windows',
                'n4_candidate_findings','n4_budget_buckets','n4_usage_reservations'
            ] LOOP
                EXECUTE 'REVOKE ALL ON TABLE public.' || quote_ident(t) ||
                        ' FROM ' || quote_ident(r);
            END LOOP;
        END IF;
    END LOOP;
END $do$;
