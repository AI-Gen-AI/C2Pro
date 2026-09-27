-- #714 trusted-state envelope on document_artifacts ("persisted != trusted").
-- Mirror of apps/api/alembic/versions/20260927_0714_document_artifact_trust_state.py.
-- Alembic remains authoritative. The Alembic revision additionally backfills
-- artifact_hash and reclassifies legacy pre-#714 HITL candidates (pending ->
-- proposed + review binding, rejected -> rejected, prior trusted restored);
-- that data step needs the application digest and is Alembic-only. Preview
-- databases built from this mirror start without legacy artifacts.

ALTER TABLE public.document_artifacts
    ADD COLUMN IF NOT EXISTS artifact_version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS artifact_hash varchar(64) NULL,
    ADD COLUMN IF NOT EXISTS trust_state varchar(20) NOT NULL DEFAULT 'trusted',
    ADD COLUMN IF NOT EXISTS scoring jsonb NULL;

UPDATE public.document_artifacts d
   SET artifact_version = v.rn
  FROM (
        SELECT artifact_id,
               row_number() OVER (PARTITION BY document_id ORDER BY created_at, artifact_id) AS rn
          FROM public.document_artifacts
       ) v
 WHERE d.artifact_id = v.artifact_id;

ALTER TABLE public.document_artifacts
    DROP CONSTRAINT IF EXISTS ck_document_artifacts_trust_state;
ALTER TABLE public.document_artifacts
    ADD CONSTRAINT ck_document_artifacts_trust_state
    CHECK (trust_state IN ('proposed','trusted','rejected','superseded'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_document_artifacts_document_version
    ON public.document_artifacts (document_id, artifact_version);

DROP INDEX IF EXISTS public.uq_document_artifacts_active_document;
CREATE UNIQUE INDEX uq_document_artifacts_active_document
    ON public.document_artifacts (document_id)
    WHERE lifecycle_status = 'active' AND trust_state = 'trusted';

CREATE UNIQUE INDEX IF NOT EXISTS uq_document_artifacts_proposed_document
    ON public.document_artifacts (document_id)
    WHERE trust_state = 'proposed';

-- Durable trusted -> ProjectGraph obligations (internal routing only; same
-- pattern as system_recovery.document_work_index). No PUBLIC access.
CREATE SCHEMA IF NOT EXISTS system_recovery;
REVOKE ALL ON SCHEMA system_recovery FROM PUBLIC;

CREATE TABLE IF NOT EXISTS system_recovery.trusted_projection_index (
    artifact_id uuid PRIMARY KEY
        REFERENCES public.document_artifacts(artifact_id) ON DELETE CASCADE,
    document_id uuid NOT NULL,
    project_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    artifact_version integer NOT NULL,
    artifact_hash varchar(64) NOT NULL,
    projection_state varchar(16) NOT NULL DEFAULT 'pending',
    enqueue_attempts integer NOT NULL DEFAULT 0,
    last_checked_at timestamp without time zone NULL,
    created_at timestamp without time zone NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at timestamp without time zone NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT ck_trusted_projection_index_state
        CHECK (projection_state IN ('pending','projected','obsolete'))
);

CREATE INDEX IF NOT EXISTS ix_trusted_projection_index_pending
    ON system_recovery.trusted_projection_index (projection_state, last_checked_at, created_at);

REVOKE ALL ON TABLE system_recovery.trusted_projection_index FROM PUBLIC;
