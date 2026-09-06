-- C1 (Option-C runtime RLS completeness) pre-fix fixture.
--
-- Reproduces, on a disposable database, the exact pre-fix schema and RLS
-- policies for the 4 tables whose Alembic-created policies reference the
-- wrong GUC name (`app.current_tenant_id` instead of `app.current_tenant`):
-- dlq_failed_tasks, wbs_nodes, notification_configs, disclaimer_acceptances.
--
-- Policy bodies below are copied verbatim from the original creating
-- migrations (20260405_0002, 20260406_0001, 20260406_0003, 20260807_0001) --
-- this is the bug reproduction, not a hypothetical.
--
-- Seeds two tenants (A, B) with one row per table per tenant so RED/GREEN
-- checks can assert both "correct tenant sees its own row" and "wrong tenant
-- does not see the other tenant's row".

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── minimal tenants/projects (wbs_nodes FKs into both) ──────────────────────
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    subscription_plan VARCHAR(50) NOT NULL DEFAULT 'free'
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    project_type VARCHAR(50) NOT NULL DEFAULT 'construction',
    status VARCHAR(50) NOT NULL DEFAULT 'active'
);

INSERT INTO tenants (id, name, slug, subscription_plan) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-000000000001', 'Tenant A', 'tenant-a', 'free'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-000000000002', 'Tenant B', 'tenant-b', 'free');

INSERT INTO projects (id, tenant_id, name) VALUES
    ('cccccccc-cccc-cccc-cccc-00000000000a', 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001', 'Project A'),
    ('cccccccc-cccc-cccc-cccc-00000000000b', 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002', 'Project B');

-- ── dlq_failed_tasks (20260405_0002, pre-fix) ────────────────────────────────
CREATE TABLE dlq_failed_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    document_id UUID,
    payload_json JSONB NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_retry_at TIMESTAMPTZ
);
ALTER TABLE dlq_failed_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY dlq_tenant_isolation ON dlq_failed_tasks
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

INSERT INTO dlq_failed_tasks (tenant_id, task_type, payload_json, error_message) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-000000000001', 'document_analysis', '{}'::jsonb, 'boom-a'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-000000000002', 'document_analysis', '{}'::jsonb, 'boom-b');

-- ── wbs_nodes (20260406_0001, pre-fix) ───────────────────────────────────────
CREATE TABLE wbs_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    lft INTEGER NOT NULL,
    rgt INTEGER NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0,
    parent_id UUID REFERENCES wbs_nodes(id) ON DELETE SET NULL
);
ALTER TABLE wbs_nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY wbs_nodes_tenant_isolation ON wbs_nodes
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

INSERT INTO wbs_nodes (project_id, tenant_id, code, name, lft, rgt) VALUES
    ('cccccccc-cccc-cccc-cccc-00000000000a', 'aaaaaaaa-aaaa-aaaa-aaaa-000000000001', 'A.1', 'Root A', 1, 2),
    ('cccccccc-cccc-cccc-cccc-00000000000b', 'bbbbbbbb-bbbb-bbbb-bbbb-000000000002', 'B.1', 'Root B', 1, 2);

-- ── notification_configs (20260406_0003, pre-fix -- no missing_ok arg) ──────
CREATE TABLE notification_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE,
    notification_channels JSONB NOT NULL DEFAULT '[]'::jsonb
);
ALTER TABLE notification_configs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON notification_configs
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

INSERT INTO notification_configs (tenant_id) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-000000000001'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-000000000002');

-- ── disclaimer_acceptances (20260807_0001, pre-fix) ─────────────────────────
CREATE TABLE disclaimer_acceptances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    project_id VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    CONSTRAINT uq_disclaimer_acceptance UNIQUE (tenant_id, user_id, project_id, version)
);
ALTER TABLE disclaimer_acceptances ENABLE ROW LEVEL SECURITY;
ALTER TABLE disclaimer_acceptances FORCE ROW LEVEL SECURITY;
CREATE POLICY disclaimer_tenant_isolation_select ON disclaimer_acceptances
    FOR SELECT USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);
CREATE POLICY disclaimer_tenant_isolation_insert ON disclaimer_acceptances
    FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

INSERT INTO disclaimer_acceptances (tenant_id, user_id, project_id, version) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-000000000001', 'dddddddd-dddd-dddd-dddd-000000000001', 'proj-a', 'v1'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-000000000002', 'dddddddd-dddd-dddd-dddd-000000000002', 'proj-b', 'v1');

-- ── synthetic non-owning, NOBYPASSRLS candidate role (mirrors p0_sec_b_gate) ─
DO $c1_role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_sec_rls_test') THEN
        CREATE ROLE c2pro_sec_rls_test NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB LOGIN;
    END IF;
END $c1_role$;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    dlq_failed_tasks, wbs_nodes, notification_configs, disclaimer_acceptances,
    tenants, projects
    TO c2pro_sec_rls_test;
