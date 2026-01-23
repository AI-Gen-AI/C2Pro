-- ===================================
-- Migration 005: RLS Policies for Test Environment
-- ===================================
-- Creates RLS policies using current_setting('app.current_tenant')
-- instead of auth.jwt() for test environment compatibility
-- Date: 2026-01-07

-- ===================================
-- 1. TENANTS TABLE
-- ===================================
-- Allow all operations on tenants table for test fixtures
-- In production, this should be more restrictive
DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants;
CREATE POLICY tenant_isolation_tenants ON tenants
    FOR ALL
    USING (TRUE)
    WITH CHECK (TRUE);

-- ===================================
-- 2. USERS TABLE
-- ===================================
-- Allow all operations on users table for test fixtures
-- In production, this should be more restrictive
DROP POLICY IF EXISTS tenant_isolation_users ON users;
CREATE POLICY tenant_isolation_users ON users
    FOR ALL
    USING (TRUE)
    WITH CHECK (TRUE);

-- ===================================
-- 3. PROJECTS TABLE
-- ===================================
-- Allow operations without tenant context (for test fixtures)
-- Enforce strict isolation when tenant context is set
DROP POLICY IF EXISTS tenant_isolation_projects ON projects;
CREATE POLICY tenant_isolation_projects ON projects
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE tenant_id = current_setting('app.current_tenant')::uuid
        END
    )
    WITH CHECK (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE tenant_id = current_setting('app.current_tenant')::uuid
        END
    );

-- ===================================
-- 4. DOCUMENTS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_documents ON documents;
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE project_id IN (
                SELECT id FROM projects WHERE tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 5. CLAUSES TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_clauses ON clauses;
CREATE POLICY tenant_isolation_clauses ON clauses
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE document_id IN (
                SELECT d.id FROM documents d
                JOIN projects p ON d.project_id = p.id
                WHERE p.tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 6. ANALYSES TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_analyses ON analyses;
CREATE POLICY tenant_isolation_analyses ON analyses
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE project_id IN (
                SELECT id FROM projects WHERE tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 7. ALERTS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_alerts ON alerts;
CREATE POLICY tenant_isolation_alerts ON alerts
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE analysis_id IN (
                SELECT a.id FROM analyses a
                JOIN projects p ON a.project_id = p.id
                WHERE p.tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 8. EXTRACTIONS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_extractions ON extractions;
CREATE POLICY tenant_isolation_extractions ON extractions
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE document_id IN (
                SELECT d.id FROM documents d
                JOIN projects p ON d.project_id = p.id
                WHERE p.tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 9. STAKEHOLDERS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_stakeholders ON stakeholders;
CREATE POLICY tenant_isolation_stakeholders ON stakeholders
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE project_id IN (
                SELECT id FROM projects WHERE tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 10. WBS_ITEMS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_wbs_items ON wbs_items;
CREATE POLICY tenant_isolation_wbs_items ON wbs_items
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE project_id IN (
                SELECT id FROM projects WHERE tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 11. BOM_ITEMS TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_bom_items ON bom_items;
CREATE POLICY tenant_isolation_bom_items ON bom_items
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE project_id IN (
                SELECT id FROM projects WHERE tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
    );

-- ===================================
-- 12. STAKEHOLDER_WBS_RACI TABLE
-- ===================================
DROP POLICY IF EXISTS tenant_isolation_stakeholder_wbs_raci ON stakeholder_wbs_raci;
CREATE POLICY tenant_isolation_stakeholder_wbs_raci ON stakeholder_wbs_raci
    FOR ALL
    USING (
        CASE
            WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
            ELSE wbs_item_id IN (
                SELECT w.id FROM wbs_items w
                JOIN projects p ON w.project_id = p.id
                WHERE p.tenant_id = current_setting('app.current_tenant')::uuid
            )
        END
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
            USING (
                CASE
                    WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
                    ELSE tenant_id = current_setting('app.current_tenant')::uuid
                END
            );
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
            USING (
                CASE
                    WHEN current_setting('app.current_tenant', TRUE) IS NULL THEN TRUE
                    ELSE tenant_id = current_setting('app.current_tenant')::uuid
                END
            );
    END IF;
END $$;

-- ===================================
-- 15. FORCE RLS (even for superusers)
-- ===================================
-- This is critical for test environment where the database user is a superuser
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE clauses FORCE ROW LEVEL SECURITY;
ALTER TABLE analyses FORCE ROW LEVEL SECURITY;
ALTER TABLE alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE extractions FORCE ROW LEVEL SECURITY;
ALTER TABLE stakeholders FORCE ROW LEVEL SECURITY;
ALTER TABLE wbs_items FORCE ROW LEVEL SECURITY;
ALTER TABLE bom_items FORCE ROW LEVEL SECURITY;
ALTER TABLE stakeholder_wbs_raci FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'ai_usage_logs'
    ) THEN
        ALTER TABLE ai_usage_logs FORCE ROW LEVEL SECURITY;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'audit_logs'
    ) THEN
        ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
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

    RAISE NOTICE 'RLS policies created: %', policy_count;
    RAISE NOTICE '✓ RLS policies configured for test environment';
    RAISE NOTICE '✓ FORCE ROW LEVEL SECURITY enabled for all tables';
END $$;
