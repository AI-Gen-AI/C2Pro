-- Lane C / C3b-1: durable, artifact-keyed materialization of an approved candidate.
-- Mirror of apps/api/alembic/versions/20261004_0002_trusted_artifact_materialization.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE system_recovery.trusted_projection_index
    ADD COLUMN materialization_state varchar(24) NOT NULL DEFAULT 'not_required',
    ADD COLUMN materialization_attempts integer NOT NULL DEFAULT 0,
    ADD COLUMN materialization_checked_at timestamp without time zone NULL,
    ADD COLUMN materialized_analysis_id uuid NULL,
    ADD COLUMN materialization_detail jsonb NULL;

ALTER TABLE system_recovery.trusted_projection_index
    ADD CONSTRAINT ck_trusted_projection_index_materialization_state
    CHECK (materialization_state IN ('not_required', 'pending', 'materialized', 'obsolete', 'operator_required'));

CREATE INDEX ix_trusted_projection_index_materialization_pending
    ON system_recovery.trusted_projection_index (materialization_checked_at, created_at)
    WHERE materialization_state = 'pending';

ALTER TABLE public.document_artifacts
    ADD CONSTRAINT uq_document_artifacts_scope UNIQUE (artifact_id, tenant_id, project_id);

ALTER TABLE public.analyses ADD COLUMN source_artifact_id uuid NULL;

ALTER TABLE public.analyses
    ADD CONSTRAINT fk_analyses_source_artifact_scope
    FOREIGN KEY (source_artifact_id, tenant_id, project_id)
    REFERENCES public.document_artifacts (artifact_id, tenant_id, project_id)
    ON DELETE RESTRICT;

CREATE UNIQUE INDEX uq_analyses_source_artifact
    ON public.analyses (source_artifact_id)
    WHERE source_artifact_id IS NOT NULL;
