-- P0-SEC-B pre-state fixture.
--
-- Reproduces the production COALESCE fail-open state for the 6 affected
-- tables and the 4 excess-policy tables so the fail-closed migration can be
-- validated forward/backward on a disposable database.
--
-- Designed to be loaded by the p0_sec_b_gate.py script into an empty
-- database owned by a superuser connection.  Never load against production.
--
-- Test UUIDs:
--   TENANT_A: aaaaaaaa-aaaa-aaaa-aaaa-000000000001
--   TENANT_B: bbbbbbbb-bbbb-bbbb-bbbb-000000000002
--   PROJECT_A: cccccccc-cccc-cccc-cccc-000000000001  (belongs to TENANT_A)
--   PROJECT_B: dddddddd-dddd-dddd-dddd-000000000002  (belongs to TENANT_B)

-- ----------------------------------------------------------------- test role
-- c2pro_sec_rls_test: NOSUPERUSER, no BYPASSRLS, login with empty password
-- (gate connects to disposable DB only; no security concern for a test role).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_sec_rls_test') THEN
        CREATE ROLE c2pro_sec_rls_test LOGIN PASSWORD '' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END $$;

-- ----------------------------------------------------------------- projects stub
-- Required for the P0-SEC-B consistency precondition check.
CREATE TABLE IF NOT EXISTS projects (
    id        uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    name      text NOT NULL DEFAULT 'stub'
);

INSERT INTO projects (id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- ========================================================== 6 COALESCE tables

-- COALESCE fail-open expression (the pre-migration form)
-- tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)

-- ---------------------------------------------------- project_states
CREATE TABLE project_states (
    state_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       uuid NOT NULL,
    tenant_id        uuid NOT NULL,
    lifecycle_status text NOT NULL DEFAULT 'active',
    created_at       timestamp NOT NULL DEFAULT now(),
    updated_at       timestamp NOT NULL DEFAULT now()
);
ALTER TABLE project_states ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_states_select ON project_states FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_states_insert ON project_states FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_states_update ON project_states FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_states_delete ON project_states FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- ------------------------------------------------ project_state_entities
CREATE TABLE project_state_entities (
    entity_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    state_id   uuid NOT NULL,
    project_id uuid NOT NULL,
    tenant_id  uuid NOT NULL,
    entity_type text NOT NULL DEFAULT 'stub',
    created_at timestamp NOT NULL DEFAULT now()
);
ALTER TABLE project_state_entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY pse_select ON project_state_entities FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY pse_insert ON project_state_entities FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY pse_update ON project_state_entities FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY pse_delete ON project_state_entities FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- -------------------------------------------------- document_revisions
CREATE TABLE document_revisions (
    revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL,
    project_id  uuid NOT NULL,
    tenant_id   uuid NOT NULL,
    rev_no      int NOT NULL DEFAULT 1,
    blob_hash   text NOT NULL DEFAULT 'sha256:stub',
    blob_key    text NOT NULL DEFAULT 'stub',
    valid_from  timestamp NOT NULL DEFAULT now(),
    valid_to    timestamp,
    created_at  timestamp NOT NULL DEFAULT now()
);
ALTER TABLE document_revisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY docrev_select ON document_revisions FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY docrev_insert ON document_revisions FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY docrev_update ON document_revisions FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY docrev_delete ON document_revisions FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- ---------------------------------------------------- project_events
-- Has a BEFORE UPDATE OR DELETE trigger (append-only enforcement).
CREATE TABLE project_events (
    event_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    tenant_id  uuid NOT NULL,
    event_type text NOT NULL DEFAULT 'stub',
    payload    jsonb NOT NULL DEFAULT '{}',
    occurred_at timestamp NOT NULL DEFAULT now(),
    created_at  timestamp NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION prevent_project_events_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'project_events is append-only';
END;
$$;
CREATE TRIGGER trg_project_events_immutable
    BEFORE UPDATE OR DELETE ON project_events
    FOR EACH ROW EXECUTE FUNCTION prevent_project_events_mutation();

ALTER TABLE project_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_events_select ON project_events FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_events_insert ON project_events FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_events_update ON project_events FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_events_delete ON project_events FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- -------------------------------------------------- project_snapshots
-- Partitioned table. Has a BEFORE UPDATE trigger (insert-only enforcement).
CREATE TABLE project_snapshots (
    snapshot_id  uuid NOT NULL,
    project_id   uuid NOT NULL,
    tenant_id    uuid NOT NULL,
    captured_at  timestamp NOT NULL,
    trigger      varchar(40) NOT NULL DEFAULT 'scheduled',
    health_vector jsonb NOT NULL DEFAULT '{}',
    created_at   timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_id, captured_at)
) PARTITION BY RANGE (captured_at);
CREATE TABLE project_snapshots_default PARTITION OF project_snapshots DEFAULT;
CREATE TABLE project_snapshots_2026_06 PARTITION OF project_snapshots
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE project_snapshots_2026_07 PARTITION OF project_snapshots
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE project_snapshots_2026_08 PARTITION OF project_snapshots
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE OR REPLACE FUNCTION prevent_project_snapshots_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'project_snapshots is insert-only';
END;
$$;
CREATE TRIGGER trg_project_snapshots_immutable
    BEFORE UPDATE ON project_snapshots
    FOR EACH ROW EXECUTE FUNCTION prevent_project_snapshots_update();

ALTER TABLE project_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_snapshots_select ON project_snapshots FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_snapshots_insert ON project_snapshots FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_snapshots_update ON project_snapshots FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_snapshots_delete ON project_snapshots FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- -------------------------------------------------- document_artifacts
CREATE TABLE document_artifacts (
    artifact_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      uuid NOT NULL,
    project_id       uuid NOT NULL,
    tenant_id        uuid NOT NULL,
    payload          jsonb NOT NULL DEFAULT '{}',
    lifecycle_status text NOT NULL DEFAULT 'active',
    created_at       timestamp NOT NULL DEFAULT now()
);
ALTER TABLE document_artifacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY document_artifacts_select ON document_artifacts FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY document_artifacts_insert ON document_artifacts FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY document_artifacts_update ON document_artifacts FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY document_artifacts_delete ON document_artifacts FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- ====================================================== 4 duplicate-policy tables
-- Each has 4 canonical NULLIF per-operation policies + 1 (or 2) excess FOR ALL.

-- ------------------------------------------------------------ analyses
CREATE TABLE analyses (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (id),
    tenant_id  uuid NOT NULL,
    status     text NOT NULL DEFAULT 'pending',
    created_at timestamp NOT NULL DEFAULT now()
);
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
-- Canonical CRUD (NULLIF — fail-closed):
CREATE POLICY analyses_tenant_isolation_select ON analyses
    FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY analyses_tenant_isolation_insert ON analyses
    FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY analyses_tenant_isolation_update ON analyses
    FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY analyses_tenant_isolation_delete ON analyses
    FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
-- Excess FOR ALL (from 20260403_0002):
CREATE POLICY tenant_isolation_analyses ON analyses
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- -------------------------------------------------------------- alerts
CREATE TABLE alerts (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (id),
    tenant_id  uuid NOT NULL,
    message    text NOT NULL DEFAULT 'stub',
    created_at timestamp NOT NULL DEFAULT now()
);
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY alerts_tenant_isolation_select ON alerts
    FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY alerts_tenant_isolation_insert ON alerts
    FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY alerts_tenant_isolation_update ON alerts
    FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY alerts_tenant_isolation_delete ON alerts
    FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY tenant_isolation_alerts ON alerts
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ------------------------------------------------------- coherence_results
CREATE TABLE coherence_results (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (id),
    tenant_id  uuid NOT NULL,
    score      float NOT NULL DEFAULT 0.0,
    created_at timestamp NOT NULL DEFAULT now()
);
ALTER TABLE coherence_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY coherence_results_tenant_isolation_select ON coherence_results
    FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY coherence_results_tenant_isolation_insert ON coherence_results
    FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY coherence_results_tenant_isolation_update ON coherence_results
    FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY coherence_results_tenant_isolation_delete ON coherence_results
    FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY tenant_isolation_coherence_results ON coherence_results
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- --------------------------------------------------- clause_embeddings
CREATE TABLE clause_embeddings (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (id),
    tenant_id  uuid NOT NULL,
    embedding  text NOT NULL DEFAULT 'stub',
    created_at timestamp NOT NULL DEFAULT now()
);
ALTER TABLE clause_embeddings ENABLE ROW LEVEL SECURITY;
CREATE POLICY clause_embeddings_tenant_isolation_select ON clause_embeddings
    FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY clause_embeddings_tenant_isolation_insert ON clause_embeddings
    FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY clause_embeddings_tenant_isolation_update ON clause_embeddings
    FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY clause_embeddings_tenant_isolation_delete ON clause_embeddings
    FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
-- Two excess FOR ALL policies (from 20260403_0002 + 20260421_0001):
CREATE POLICY tenant_isolation_clause_embeddings ON clause_embeddings
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY clause_embeddings_tenant_isolation ON clause_embeddings
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ================================================================== seed rows
-- Two rows per table: one for TENANT_A, one for TENANT_B.
-- Inserted as superuser (BYPASSRLS) so they bypass the COALESCE policies.

-- project_states
INSERT INTO project_states (project_id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- project_state_entities
INSERT INTO project_state_entities (state_id, project_id, tenant_id) VALUES
    (gen_random_uuid(), 'cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    (gen_random_uuid(), 'dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- document_revisions
INSERT INTO document_revisions (document_id, project_id, tenant_id) VALUES
    (gen_random_uuid(), 'cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    (gen_random_uuid(), 'dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- project_events
INSERT INTO project_events (project_id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- project_snapshots (insert into default partition: captured_at far future)
INSERT INTO project_snapshots (snapshot_id, project_id, tenant_id, captured_at) VALUES
    (gen_random_uuid(), 'cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid, '2030-01-15'),
    (gen_random_uuid(), 'dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid, '2030-01-15');

-- document_artifacts
INSERT INTO document_artifacts (document_id, project_id, tenant_id) VALUES
    (gen_random_uuid(), 'cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    (gen_random_uuid(), 'dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- analyses / alerts / coherence_results / clause_embeddings
INSERT INTO analyses (project_id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

INSERT INTO alerts (project_id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

INSERT INTO coherence_results (project_id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

INSERT INTO clause_embeddings (project_id, tenant_id) VALUES
    ('cccccccc-cccc-cccc-cccc-000000000001'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001'::uuid),
    ('dddddddd-dddd-dddd-dddd-000000000002'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002'::uuid);

-- ================================================================= test grants
-- Grant the minimal privileges the test role needs to exercise RLS.
GRANT USAGE ON SCHEMA public TO c2pro_sec_rls_test;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    project_states,
    project_state_entities,
    document_revisions,
    project_events,
    project_snapshots,
    project_snapshots_default,
    project_snapshots_2026_06,
    project_snapshots_2026_07,
    project_snapshots_2026_08,
    document_artifacts,
    analyses,
    alerts,
    coherence_results,
    clause_embeddings
TO c2pro_sec_rls_test;
GRANT SELECT ON projects TO c2pro_sec_rls_test;
