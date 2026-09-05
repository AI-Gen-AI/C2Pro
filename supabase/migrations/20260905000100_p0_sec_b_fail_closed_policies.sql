-- P0-SEC-B: replace 24 fail-open COALESCE RLS policies with fail-closed NULLIF.
--
-- GENERATED FILE -- DO NOT EDIT BY HAND.
-- Canonical source: apps/api/alembic/versions/20260905_0001_p0_sec_b_fail_closed_policies.py
-- Regenerate with:  python apps/api/scripts/generate_p0_sec_b_mirror.py
-- Parity is enforced by apps/api/tests/security/test_p0_sec_b_fail_closed_migration.py
--
-- Audit record: docs/security/P0-SEC-B-fail-closed-policies.md

DO $p0secb_pre$
        DECLARE
            v_bad   bigint;
            v_table text;
        BEGIN
            -- If projects table is absent (non-production environment without
            -- the full schema), skip the check — no mismatches can exist.
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = 'projects'
            ) THEN
                RETURN;
            END IF;

            FOREACH v_table IN ARRAY ARRAY['analyses', 'alerts', 'coherence_results', 'clause_embeddings']
            LOOP
                -- tenant_id vs project.tenant_id mismatch check
                EXECUTE
                    'SELECT COUNT(*) FROM public.' || quote_ident(v_table) ||
                    ' t JOIN public.projects p ON p.id = t.project_id'
                    ' WHERE t.tenant_id IS DISTINCT FROM p.tenant_id'
                INTO v_bad;
                IF v_bad > 0 THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'P0-SEC-B PRECONDITION FAILED: table ' || v_table ||
                        ' has ' || v_bad::text ||
                        ' row(s) where tenant_id IS DISTINCT FROM projects.tenant_id.'
                        ' Inspect and reconcile before re-running this migration.';
                END IF;

                -- orphaned project_id check
                EXECUTE
                    'SELECT COUNT(*) FROM public.' || quote_ident(v_table) ||
                    ' t WHERE t.project_id IS NOT NULL'
                    ' AND NOT EXISTS ('
                    'SELECT 1 FROM public.projects p WHERE p.id = t.project_id)'
                INTO v_bad;
                IF v_bad > 0 THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'P0-SEC-B PRECONDITION FAILED: table ' || v_table ||
                        ' has ' || v_bad::text ||
                        ' orphaned project_id(s) with no matching projects row.'
                        ' Inspect and reconcile before re-running this migration.';
                END IF;
            END LOOP;
        END $p0secb_pre$;

SET LOCAL lock_timeout = '30s';

DROP POLICY IF EXISTS project_states_select ON project_states;

CREATE POLICY project_states_select ON project_states FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_states_insert ON project_states;

CREATE POLICY project_states_insert ON project_states FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_states_update ON project_states;

CREATE POLICY project_states_update ON project_states FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_states_delete ON project_states;

CREATE POLICY project_states_delete ON project_states FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS pse_select ON project_state_entities;

CREATE POLICY pse_select ON project_state_entities FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS pse_insert ON project_state_entities;

CREATE POLICY pse_insert ON project_state_entities FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS pse_update ON project_state_entities;

CREATE POLICY pse_update ON project_state_entities FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS pse_delete ON project_state_entities;

CREATE POLICY pse_delete ON project_state_entities FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS docrev_select ON document_revisions;

CREATE POLICY docrev_select ON document_revisions FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS docrev_insert ON document_revisions;

CREATE POLICY docrev_insert ON document_revisions FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS docrev_update ON document_revisions;

CREATE POLICY docrev_update ON document_revisions FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS docrev_delete ON document_revisions;

CREATE POLICY docrev_delete ON document_revisions FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_events_select ON project_events;

CREATE POLICY project_events_select ON project_events FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_events_insert ON project_events;

CREATE POLICY project_events_insert ON project_events FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_events_update ON project_events;

CREATE POLICY project_events_update ON project_events FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_events_delete ON project_events;

CREATE POLICY project_events_delete ON project_events FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_snapshots_select ON project_snapshots;

CREATE POLICY project_snapshots_select ON project_snapshots FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_snapshots_insert ON project_snapshots;

CREATE POLICY project_snapshots_insert ON project_snapshots FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_snapshots_update ON project_snapshots;

CREATE POLICY project_snapshots_update ON project_snapshots FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS project_snapshots_delete ON project_snapshots;

CREATE POLICY project_snapshots_delete ON project_snapshots FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_artifacts_select ON document_artifacts;

CREATE POLICY document_artifacts_select ON document_artifacts FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_artifacts_insert ON document_artifacts;

CREATE POLICY document_artifacts_insert ON document_artifacts FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_artifacts_update ON document_artifacts;

CREATE POLICY document_artifacts_update ON document_artifacts FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_artifacts_delete ON document_artifacts;

CREATE POLICY document_artifacts_delete ON document_artifacts FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation_analyses ON analyses;

DROP POLICY IF EXISTS tenant_isolation_alerts ON alerts;

DROP POLICY IF EXISTS tenant_isolation_coherence_results ON coherence_results;

DROP POLICY IF EXISTS tenant_isolation_clause_embeddings ON clause_embeddings;

DROP POLICY IF EXISTS clause_embeddings_tenant_isolation ON clause_embeddings;
