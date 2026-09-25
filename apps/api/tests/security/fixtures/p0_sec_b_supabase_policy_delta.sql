-- P0-SEC-B Supabase-historical policy delta (PATH B).
--
-- Applied ON TOP of p0_sec_b_prestate.sql (Alembic base).
-- Replaces the 24 COALESCE short-named policies with the 24 NULLIF
-- *_tenant_isolation_* policies created by the June 2026 Supabase CLI
-- migrations (20260613000100, 20260614000100).
--
-- Historical UPDATE policies carry BOTH USING AND WITH CHECK — the Supabase
-- CLI emitted both clauses, which is a faithful reproduction of what a
-- Supabase-path DB looks like before P0-SEC-B is applied.
--
-- After this delta the database is semantically identical to what
-- p0_sec_b_supabase_prestate.sql produced, but without duplicating the
-- shared DDL infrastructure from p0_sec_b_prestate.sql.

-- --------------------------------------------------------- project_states
DROP POLICY project_states_select ON project_states;
DROP POLICY project_states_insert ON project_states;
DROP POLICY project_states_update ON project_states;
DROP POLICY project_states_delete ON project_states;

CREATE POLICY project_states_tenant_isolation_select ON project_states FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_states_tenant_isolation_insert ON project_states FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_states_tenant_isolation_update ON project_states FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_states_tenant_isolation_delete ON project_states FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ------------------------------------------------- project_state_entities
DROP POLICY pse_select ON project_state_entities;
DROP POLICY pse_insert ON project_state_entities;
DROP POLICY pse_update ON project_state_entities;
DROP POLICY pse_delete ON project_state_entities;

CREATE POLICY project_state_entities_tenant_isolation_select ON project_state_entities FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_state_entities_tenant_isolation_insert ON project_state_entities FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_state_entities_tenant_isolation_update ON project_state_entities FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_state_entities_tenant_isolation_delete ON project_state_entities FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ---------------------------------------------------- document_revisions
DROP POLICY docrev_select ON document_revisions;
DROP POLICY docrev_insert ON document_revisions;
DROP POLICY docrev_update ON document_revisions;
DROP POLICY docrev_delete ON document_revisions;

CREATE POLICY document_revisions_tenant_isolation_select ON document_revisions FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY document_revisions_tenant_isolation_insert ON document_revisions FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY document_revisions_tenant_isolation_update ON document_revisions FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY document_revisions_tenant_isolation_delete ON document_revisions FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ------------------------------------------------------ project_events
DROP POLICY project_events_select ON project_events;
DROP POLICY project_events_insert ON project_events;
DROP POLICY project_events_update ON project_events;
DROP POLICY project_events_delete ON project_events;

CREATE POLICY project_events_tenant_isolation_select ON project_events FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_events_tenant_isolation_insert ON project_events FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_events_tenant_isolation_update ON project_events FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_events_tenant_isolation_delete ON project_events FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- ---------------------------------------------------- project_snapshots
DROP POLICY project_snapshots_select ON project_snapshots;
DROP POLICY project_snapshots_insert ON project_snapshots;
DROP POLICY project_snapshots_update ON project_snapshots;
DROP POLICY project_snapshots_delete ON project_snapshots;

CREATE POLICY project_snapshots_tenant_isolation_select ON project_snapshots FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_snapshots_tenant_isolation_insert ON project_snapshots FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_snapshots_tenant_isolation_update ON project_snapshots FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY project_snapshots_tenant_isolation_delete ON project_snapshots FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- --------------------------------------------------- document_artifacts
DROP POLICY document_artifacts_select ON document_artifacts;
DROP POLICY document_artifacts_insert ON document_artifacts;
DROP POLICY document_artifacts_update ON document_artifacts;
DROP POLICY document_artifacts_delete ON document_artifacts;

CREATE POLICY document_artifacts_tenant_isolation_select ON document_artifacts FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY document_artifacts_tenant_isolation_insert ON document_artifacts FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY document_artifacts_tenant_isolation_update ON document_artifacts FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
CREATE POLICY document_artifacts_tenant_isolation_delete ON document_artifacts FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
