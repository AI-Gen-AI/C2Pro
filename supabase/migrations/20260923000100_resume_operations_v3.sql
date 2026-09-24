-- V3 durable resume model: fenced operations, attempt ledger, provenance.
-- Mirror of apps/api/alembic/versions/20260923_0001_resume_operations_v3.py (Alembic is authoritative; keep in sync).

CREATE TABLE IF NOT EXISTS public.resume_operations (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    -- Identity: the EXACT review row. item_id is a business key and is NOT
    -- unique across legacy duplicates.
    review_row_id uuid NOT NULL,
    project_id uuid,
    document_id uuid,
    thread_id varchar(512),
    -- The IMMUTABLE human-interrupt checkpoint: the only checkpoint a new
    -- attempt may ever restart from.
    source_checkpoint_id varchar(255),
    -- Terminal checkpoint of the attempt that actually finished.
    terminal_checkpoint_id varchar(255),
    -- Current ownership.
    current_attempt_id uuid,
    owner_token uuid,
    -- Quoted literal so the stored default renders as '0'::bigint,
    -- byte-identical to the Alembic server_default.
    fencing_token bigint NOT NULL DEFAULT '0',
    decision_revision integer NOT NULL DEFAULT 1,
    decision varchar(32),
    decision_hash varchar(128),
    reviewer varchar(256),
    phase varchar(40) NOT NULL,
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    -- Durable business outcome.
    analysis_id uuid,
    failure_count integer NOT NULL DEFAULT 0,
    last_error text,
    next_attempt_at timestamptz,
    operation_metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_resume_operations_tenant_id
    ON public.resume_operations (tenant_id);

-- One lifecycle row per review row.
CREATE UNIQUE INDEX IF NOT EXISTS uq_resume_operations_review_row
    ON public.resume_operations (review_row_id);

-- Reconciliation pages nonterminal operations by phase/schedule.
CREATE INDEX IF NOT EXISTS ix_resume_operations_phase_next_attempt
    ON public.resume_operations (phase, next_attempt_at);

CREATE TABLE IF NOT EXISTS public.resume_operation_attempts (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    operation_id uuid NOT NULL REFERENCES public.resume_operations (id) ON DELETE CASCADE,
    owner_token uuid NOT NULL,
    fencing_token bigint NOT NULL,
    decision_revision integer NOT NULL,
    decision varchar(32) NOT NULL,
    decision_hash varchar(128),
    reviewer varchar(256),
    source_checkpoint_id varchar(255),
    terminal_checkpoint_id varchar(255),
    -- ACTIVE | SUPERSEDED | ABANDONED | COMPLETED | FAILED
    outcome varchar(32) NOT NULL,
    reason text,
    started_at timestamptz NOT NULL,
    ended_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_resume_operation_attempts_tenant_id
    ON public.resume_operation_attempts (tenant_id);

-- The fence is monotonic per operation: two attempts can never share one.
CREATE UNIQUE INDEX IF NOT EXISTS uq_resume_attempts_operation_fence
    ON public.resume_operation_attempts (operation_id, fencing_token);

-- Multi-tenant RLS, matching the Alembic policies exactly.
ALTER TABLE public.resume_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_operation_attempts ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    t text;
    a text;
    clause text;
BEGIN
    FOREACH t IN ARRAY ARRAY['resume_operations', 'resume_operation_attempts'] LOOP
        FOREACH a IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE'] LOOP
            clause := CASE WHEN a = 'INSERT' THEN 'WITH CHECK' ELSE 'USING' END;
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public' AND tablename = t
                  AND policyname = 'tenant_isolation_' || lower(a)
            ) THEN
                EXECUTE format(
                    'CREATE POLICY %I ON public.%I FOR %s %s '
                    '(tenant_id = COALESCE('
                    'NULLIF(current_setting(''app.current_tenant'', true), '''')::uuid, tenant_id))',
                    'tenant_isolation_' || lower(a), t, a, clause
                );
            END IF;
        END LOOP;
    END LOOP;
END
$$;

-- Durable effect provenance.
ALTER TABLE public.analyses ADD COLUMN IF NOT EXISTS resume_operation_id uuid;
ALTER TABLE public.analyses ADD COLUMN IF NOT EXISTS resume_attempt_id uuid;
ALTER TABLE public.analyses ADD COLUMN IF NOT EXISTS fencing_token bigint;
ALTER TABLE public.analyses ADD COLUMN IF NOT EXISTS decision_revision integer;

-- Operation-keyed: N17 re-entry finds the existing analysis instead of
-- persisting a second one. PARTIAL so every historical and non-HITL analysis
-- is untouched and legitimate re-analyses stay possible.
CREATE UNIQUE INDEX IF NOT EXISTS uq_analyses_resume_operation
    ON public.analyses (resume_operation_id)
    WHERE resume_operation_id IS NOT NULL;

ALTER TABLE public.project_events ADD COLUMN IF NOT EXISTS resume_operation_id uuid;
ALTER TABLE public.project_events ADD COLUMN IF NOT EXISTS resume_attempt_id uuid;

-- Exactly one analysis.persisted and one graph.completed per operation.
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_events_resume_operation_type
    ON public.project_events (resume_operation_id, event_type)
    WHERE resume_operation_id IS NOT NULL;
