-- P0-SEC-A pre-state fixture.
--
-- Reproduces the production Supabase pre-state for every object inside the
-- P0-SEC-A blast radius, so the containment migration can be validated
-- forward/backward on a disposable database. Captured read-only from project
-- tcxedmnvebazcsaridge on 2026-09-02; see
-- blackboard/SESSION_2026-09-02_p0-sec-supabase-audit.md.
--
-- Role model note: production `postgres` is NOT superuser but HAS BYPASSRLS and
-- owns every public table. A local superuser would mask RLS behaviour, so the
-- fixture creates `c2pro_owner` (NOSUPERUSER + BYPASSRLS) to stand in for it and
-- mirrors production's role memberships (postgres is a member of anon /
-- authenticated / service_role / authenticator WITH ADMIN OPTION, and is NOT a
-- member of supabase_admin).

-- ---------------------------------------------------------------- roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator LOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_owner') THEN
        CREATE ROLE c2pro_owner LOGIN NOSUPERUSER BYPASSRLS CREATEROLE;
    END IF;
END $$;

GRANT anon, authenticated, service_role TO authenticator;
GRANT anon, authenticated, service_role TO c2pro_owner WITH ADMIN OPTION;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
ALTER SCHEMA public OWNER TO c2pro_owner;

-- ------------------------------------------------- default privileges (P0-SEC-03)
-- Production pg_default_acl: tables anon/authenticated/service_role = arwdDxtm,
-- sequences = rwU, functions = X. Functions are out of P0-SEC-A scope but are
-- reproduced so the migration can be proven NOT to alter them.
ALTER DEFAULT PRIVILEGES FOR ROLE c2pro_owner IN SCHEMA public
    GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE c2pro_owner IN SCHEMA public
    GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE c2pro_owner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role;

SET ROLE c2pro_owner;

-- --------------------------------------------- LangGraph checkpoint tables
-- Schema from langgraph-checkpoint-postgres. No tenant_id, no project_id, no FKs.
CREATE TABLE checkpoints (
    thread_id            text  NOT NULL,
    checkpoint_ns        text  NOT NULL DEFAULT '',
    checkpoint_id        text  NOT NULL,
    parent_checkpoint_id text,
    type                 text,
    checkpoint           jsonb NOT NULL,
    metadata             jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE checkpoint_blobs (
    thread_id     text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT '',
    channel       text NOT NULL,
    version       text NOT NULL,
    type          text NOT NULL,
    blob          bytea,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);
CREATE TABLE checkpoint_writes (
    thread_id     text    NOT NULL,
    checkpoint_ns text    NOT NULL DEFAULT '',
    checkpoint_id text    NOT NULL,
    task_id       text    NOT NULL,
    idx           integer NOT NULL,
    channel       text    NOT NULL,
    type          text,
    blob          bytea   NOT NULL,
    task_path     text    NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
CREATE TABLE checkpoint_migrations (v integer NOT NULL PRIMARY KEY);

-- The four permissive policies authored by
-- alembic/versions/20260403_0003_fix_security_definer_views_rls_infra.py:35-53
-- to clear the rls_disabled_in_public advisor ERROR. This is the exposure.
ALTER TABLE checkpoints            ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoint_blobs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoint_writes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoint_migrations  ENABLE ROW LEVEL SECURITY;
CREATE POLICY "checkpoints_select"           ON checkpoints           FOR SELECT USING (true);
CREATE POLICY "checkpoint_blobs_select"      ON checkpoint_blobs      FOR SELECT USING (true);
CREATE POLICY "checkpoint_writes_select"     ON checkpoint_writes     FOR SELECT USING (true);
CREATE POLICY "checkpoint_migrations_select" ON checkpoint_migrations FOR SELECT USING (true);

-- ------------------------------------------------- RLS-off tables (P0-SEC-01)
CREATE TABLE evidence_claims (
    claim_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL,
    project_id  uuid NOT NULL,
    document_id uuid,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE evidence_extraction_events (
    event_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL,
    project_id  uuid NOT NULL,
    document_id uuid,
    created_at  timestamptz NOT NULL DEFAULT now()
);
-- Global reference data: intentionally has no tenant_id.
CREATE TABLE category_centroids (
    category   text PRIMARY KEY,
    dimensions integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- --------------------------------------- project_snapshots partitions (P0-SEC-02)
CREATE TABLE project_events (
    event_id   uuid NOT NULL DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL,
    project_id uuid NOT NULL,
    PRIMARY KEY (event_id)
);
CREATE TABLE project_snapshots (
    snapshot_id     uuid      NOT NULL,
    project_id      uuid      NOT NULL,
    tenant_id       uuid      NOT NULL,
    captured_at     timestamp NOT NULL,
    trigger         varchar(40) NOT NULL,
    health_vector   jsonb     NOT NULL,
    source_event_id uuid REFERENCES project_events (event_id) ON DELETE SET NULL,
    created_at      timestamp NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    PRIMARY KEY (snapshot_id, captured_at)
) PARTITION BY RANGE (captured_at);
CREATE TABLE project_snapshots_default   PARTITION OF project_snapshots DEFAULT;
CREATE TABLE project_snapshots_2026_06   PARTITION OF project_snapshots FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE project_snapshots_2026_07   PARTITION OF project_snapshots FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE project_snapshots_2026_08   PARTITION OF project_snapshots FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

-- Fail-open parent policies (P0-SEC-04). NOT rewritten by P0-SEC-A; reproduced so
-- the migration can be proven to leave them untouched (that is P0-SEC-B).
ALTER TABLE project_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_snapshots_select ON project_snapshots FOR SELECT
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_snapshots_insert ON project_snapshots FOR INSERT
    WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_snapshots_update ON project_snapshots FOR UPDATE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));
CREATE POLICY project_snapshots_delete ON project_snapshots FOR DELETE
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id));

-- ---------------------------------------------- document_revisions (P0-SEC-04)
CREATE TABLE document_revisions (
    revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL,
    project_id  uuid NOT NULL,
    document_id uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
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

-- ------------------------------------------------------- waitlist (must survive)
CREATE TABLE waitlist_signups (
    id         bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    email      text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE waitlist_signups ENABLE ROW LEVEL SECURITY;  -- deny-all: EXPECTED_DENY_ALL

-- --------------------------------------------------------- a sequence in scope
CREATE SEQUENCE public.p0sec_probe_seq;

-- ------------------------------------------------------------------- seed rows
INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint)
    VALUES ('11111111-1111-1111-1111-111111111111', 'ck-1', '{"stub":true}'::jsonb);
INSERT INTO checkpoint_blobs (thread_id, channel, version, type, blob)
    VALUES ('11111111-1111-1111-1111-111111111111', 'state', '1', 'msgpack', '\x00'::bytea);
INSERT INTO checkpoint_writes (thread_id, checkpoint_id, task_id, idx, channel, blob)
    VALUES ('11111111-1111-1111-1111-111111111111', 'ck-1', 'task-1', 0, 'state', '\x00'::bytea);
INSERT INTO checkpoint_migrations (v) VALUES (1);
INSERT INTO evidence_claims (tenant_id, project_id)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-0000000000a1');
INSERT INTO evidence_extraction_events (tenant_id, project_id)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-0000000000a1');
INSERT INTO category_centroids (category, dimensions) VALUES ('payment_terms', 1536);
INSERT INTO document_revisions (tenant_id, project_id, document_id) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-0000000000a1', gen_random_uuid()),
    ('bbbbbbbb-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-0000000000b1', gen_random_uuid());
INSERT INTO project_snapshots (snapshot_id, project_id, tenant_id, captured_at, trigger, health_vector)
    VALUES (gen_random_uuid(), 'aaaaaaaa-0000-0000-0000-0000000000a1',
            'aaaaaaaa-0000-0000-0000-000000000001', '2026-08-15', 'scheduled', '{}'::jsonb);
INSERT INTO waitlist_signups (email) VALUES ('prestate@example.test');

RESET ROLE;

-- Explicit grants matching production (anon/authenticated/service_role = ALL on
-- every table + sequence in public).
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
