-- TS-E2E-SEC-TNT-001
-- Forward-only fail-closed RLS normalization for application-owned tables
--
-- This migration replaces the permissive compatibility policies introduced in
-- 005_rls_policies_for_tests.sql with fail-closed policies based on
-- current_setting('app.current_tenant', true). Auth bootstrap is handled via
-- auth_bootstrap SECURITY DEFINER helpers, not by permissive table policies.

-- ===================================
-- 1. TENANTS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants;

DROP POLICY IF EXISTS tenant_isolation_select ON tenants;
CREATE POLICY tenant_isolation_select ON tenants
    FOR SELECT
    USING (id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation_update ON tenants;
CREATE POLICY tenant_isolation_update ON tenants
    FOR UPDATE
    USING (id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation_insert ON tenants;
CREATE POLICY tenant_isolation_insert ON tenants
    FOR INSERT
    WITH CHECK (FALSE);

DROP POLICY IF EXISTS tenant_isolation_delete ON tenants;
CREATE POLICY tenant_isolation_delete ON tenants
    FOR DELETE
    USING (FALSE);

-- ===================================
-- 2. USERS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_users ON users;

DROP POLICY IF EXISTS user_tenant_isolation_select ON users;
CREATE POLICY user_tenant_isolation_select ON users
    FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS user_tenant_isolation_insert ON users;
CREATE POLICY user_tenant_isolation_insert ON users
    FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS user_tenant_isolation_update ON users;
CREATE POLICY user_tenant_isolation_update ON users
    FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS user_tenant_isolation_delete ON users;
CREATE POLICY user_tenant_isolation_delete ON users
    FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

-- ===================================
-- 3. PROJECTS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_projects ON projects;

DROP POLICY IF EXISTS project_tenant_isolation_select ON projects;
CREATE POLICY project_tenant_isolation_select ON projects
    FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS project_tenant_isolation_insert ON projects;
CREATE POLICY project_tenant_isolation_insert ON projects
    FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS project_tenant_isolation_update ON projects;
CREATE POLICY project_tenant_isolation_update ON projects
    FOR UPDATE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

DROP POLICY IF EXISTS project_tenant_isolation_delete ON projects;
CREATE POLICY project_tenant_isolation_delete ON projects
    FOR DELETE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

-- ===================================
-- 4. DOCUMENTS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_documents ON documents;
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL
    USING (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 5. CLAUSES TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_clauses ON clauses;
CREATE POLICY tenant_isolation_clauses ON clauses
    FOR ALL
    USING (
        document_id IN (
            SELECT d.id
            FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        document_id IN (
            SELECT d.id
            FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 6. ANALYSES TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_analyses ON analyses;
CREATE POLICY tenant_isolation_analyses ON analyses
    FOR ALL
    USING (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 7. ALERTS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_alerts ON alerts;
CREATE POLICY tenant_isolation_alerts ON alerts
    FOR ALL
    USING (
        analysis_id IN (
            SELECT a.id
            FROM analyses a
            JOIN projects p ON a.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        analysis_id IN (
            SELECT a.id
            FROM analyses a
            JOIN projects p ON a.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 8. EXTRACTIONS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_extractions ON extractions;
CREATE POLICY tenant_isolation_extractions ON extractions
    FOR ALL
    USING (
        document_id IN (
            SELECT d.id
            FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        document_id IN (
            SELECT d.id
            FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 9. STAKEHOLDERS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_stakeholders ON stakeholders;
CREATE POLICY tenant_isolation_stakeholders ON stakeholders
    FOR ALL
    USING (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 10. WBS_ITEMS TABLE
-- ===================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'wbs_items'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_wbs_items ON wbs_items;
        CREATE POLICY tenant_isolation_wbs_items ON wbs_items
            FOR ALL
            USING (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            )
            WITH CHECK (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'procurement_wbs_items'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_procurement_wbs_items ON procurement_wbs_items;
        CREATE POLICY tenant_isolation_procurement_wbs_items ON procurement_wbs_items
            FOR ALL
            USING (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            )
            WITH CHECK (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            );
    END IF;
END $$;

-- ===================================
-- 11. BOM_ITEMS TABLE
-- ===================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'bom_items'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_bom_items ON bom_items;
        CREATE POLICY tenant_isolation_bom_items ON bom_items
            FOR ALL
            USING (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            )
            WITH CHECK (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'procurement_bom_items'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_procurement_bom_items ON procurement_bom_items;
        CREATE POLICY tenant_isolation_procurement_bom_items ON procurement_bom_items
            FOR ALL
            USING (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            )
            WITH CHECK (
                project_id IN (
                    SELECT id
                    FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
                )
            );
    END IF;
END $$;

-- ===================================
-- 12. STAKEHOLDER_WBS_RACI TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_stakeholder_wbs_raci ON stakeholder_wbs_raci;
CREATE POLICY tenant_isolation_stakeholder_wbs_raci ON stakeholder_wbs_raci
    FOR ALL
    USING (
        wbs_item_id IN (
            SELECT w.id
            FROM wbs_items w
            JOIN projects p ON w.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    )
    WITH CHECK (
        wbs_item_id IN (
            SELECT w.id
            FROM wbs_items w
            JOIN projects p ON w.project_id = p.id
            WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid
        )
    );

-- ===================================
-- 13. AI_USAGE_LOGS TABLE
-- ===================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'ai_usage_logs'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_ai_usage_logs ON ai_usage_logs;
        CREATE POLICY tenant_isolation_ai_usage_logs ON ai_usage_logs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);
    END IF;
END $$;

-- ===================================
-- 14. AUDIT_LOGS TABLE
-- ===================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'audit_logs'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;
        CREATE POLICY tenant_isolation_audit_logs ON audit_logs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);
    END IF;
END $$;

-- ===================================
-- 15. REVIEW_ITEMS TABLE
-- ===================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'review_items'
    ) THEN
        DROP POLICY IF EXISTS tenant_isolation_select ON review_items;
        CREATE POLICY tenant_isolation_select ON review_items
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

        DROP POLICY IF EXISTS tenant_isolation_insert ON review_items;
        CREATE POLICY tenant_isolation_insert ON review_items
            FOR INSERT
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);

        DROP POLICY IF EXISTS tenant_isolation_update ON review_items;
        CREATE POLICY tenant_isolation_update ON review_items
            FOR UPDATE
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', TRUE), '')::uuid);
    END IF;
END $$;

-- ===================================
-- 16. FORCE RLS
-- ===================================
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE clauses ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE clauses FORCE ROW LEVEL SECURITY;
ALTER TABLE analyses FORCE ROW LEVEL SECURITY;
ALTER TABLE alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE extractions FORCE ROW LEVEL SECURITY;
ALTER TABLE stakeholders FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'wbs_items'
    ) THEN
        ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE wbs_items FORCE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'procurement_wbs_items'
    ) THEN
        ALTER TABLE procurement_wbs_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE procurement_wbs_items FORCE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'bom_items'
    ) THEN
        ALTER TABLE bom_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE bom_items FORCE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'procurement_bom_items'
    ) THEN
        ALTER TABLE procurement_bom_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE procurement_bom_items FORCE ROW LEVEL SECURITY;
    END IF;
END $$;
ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholder_wbs_raci FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'ai_usage_logs'
    ) THEN
        ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ai_usage_logs FORCE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'audit_logs'
    ) THEN
        ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'review_items'
    ) THEN
        ALTER TABLE review_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE review_items FORCE ROW LEVEL SECURITY;
    END IF;
END $$;

-- Verification
DO $$
DECLARE
    policy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND policyname LIKE 'tenant_isolation_%';

    RAISE NOTICE 'RLS policies present after fail-closed normalization: %', policy_count;
    RAISE NOTICE '✓ Fail-closed app.current_tenant RLS policies applied';
END $$;
