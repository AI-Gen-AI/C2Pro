-- TASK-COH-V2-SCORE-VERSION-PERSIST: v2-only shadow score persistence.
-- Refers to Suite ID: TS-INT-COH-V2-SHADOW-PERSIST-001.
-- This is intentionally separate from coherence_results so v1 latest reads
-- cannot observe a shadow score before cutover.

CREATE TABLE IF NOT EXISTS public.coherence_v2_shadow (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    coherence_score double precision NULL,
    completeness_score double precision NOT NULL,
    technical_reliability_index double precision NOT NULL,
    active_weight double precision NOT NULL,
    score_version varchar(32) NOT NULL DEFAULT 'coherence-v2',
    status varchar(64) NOT NULL,
    score_reason text NULL,
    categories_v2 jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_coherence_v2_shadow_score_version
        CHECK (score_version = 'coherence-v2')
);

CREATE INDEX IF NOT EXISTS ix_coherence_v2_shadow_tenant_project_created
    ON public.coherence_v2_shadow (tenant_id, project_id, created_at DESC);

ALTER TABLE public.coherence_v2_shadow ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coherence_v2_shadow FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS coherence_v2_shadow_tenant_isolation ON public.coherence_v2_shadow;
CREATE POLICY coherence_v2_shadow_tenant_isolation
    ON public.coherence_v2_shadow
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND project_id IN (
            SELECT id
            FROM public.projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND project_id IN (
            SELECT id
            FROM public.projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    );
