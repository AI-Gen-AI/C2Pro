-- TS-E2E-SEC-TNT-001
-- Normalize remaining application-owned RLS policies to app.current_tenant

-- Remove legacy overlapping policies on core tables where the app-managed
-- fail-closed equivalents already exist.
DROP POLICY IF EXISTS "Allow members to access their projects" ON projects;
DROP POLICY IF EXISTS "Allow individual tenant access" ON tenants;
DROP POLICY IF EXISTS tenant_self_only ON tenants;
DROP POLICY IF EXISTS "Allow users to see themselves" ON users;
DROP POLICY IF EXISTS tenant_isolation_ai_logs ON ai_usage_logs;
DROP POLICY IF EXISTS tenant_isolation_raci ON stakeholder_wbs_raci;

ALTER TABLE stakeholder_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholder_alerts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_stakeholder_alerts ON stakeholder_alerts;
CREATE POLICY tenant_isolation_stakeholder_alerts ON stakeholder_alerts
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

ALTER TABLE bom_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bom_revisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_bom_revisions ON bom_revisions;
CREATE POLICY tenant_isolation_bom_revisions ON bom_revisions
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

ALTER TABLE procurement_plan_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_plan_snapshots FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_procurement_snapshots ON procurement_plan_snapshots;
CREATE POLICY tenant_isolation_procurement_snapshots ON procurement_plan_snapshots
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

ALTER TABLE knowledge_graph_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_graph_nodes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_kg_nodes ON knowledge_graph_nodes;
CREATE POLICY tenant_isolation_kg_nodes ON knowledge_graph_nodes
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

ALTER TABLE knowledge_graph_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_graph_edges FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_kg_edges ON knowledge_graph_edges;
CREATE POLICY tenant_isolation_kg_edges ON knowledge_graph_edges
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
