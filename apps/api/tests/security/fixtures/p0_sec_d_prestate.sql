-- P0-SEC-D pre-state fixture.
--
-- Reproduces the production Supabase role model and default-privilege
-- posture relevant to public.handle_new_user(): anon / authenticated /
-- service_role exist, and newly created functions in schema public inherit
-- EXECUTE via ALTER DEFAULT PRIVILEGES, exactly as captured read-only from
-- production on 2026-09-02 (see apps/api/tests/security/fixtures/
-- p0_sec_a_prestate.sql, which this role block mirrors). A minimal
-- auth.users / public.tenants / public.users are created so the trigger
-- this function serves can actually be exercised end to end.

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
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_owner') THEN
        CREATE ROLE c2pro_owner LOGIN NOSUPERUSER BYPASSRLS CREATEROLE;
    END IF;
END $$;

GRANT anon, authenticated, service_role TO c2pro_owner WITH ADMIN OPTION;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
ALTER SCHEMA public OWNER TO c2pro_owner;

-- Production pg_default_acl: functions in schema public get EXECUTE granted
-- to anon/authenticated/service_role at creation time unless the creating
-- migration explicitly revokes it afterward.
ALTER DEFAULT PRIVILEGES FOR ROLE c2pro_owner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role;

-- ---------------------------------------------------- auth (Supabase GoTrue)
-- Owned by the superuser bootstrapping this fixture, not c2pro_owner --
-- production auth.users is platform-managed and not owned by the project
-- role either. The USAGE + INSERT granted to `authenticated` below is a
-- SYNTHETIC harness permission chosen only to exercise the trigger
-- mechanism as a non-superuser, non-owner role. It is not a claim about
-- which role or privilege model Supabase Auth's own GoTrue service
-- actually uses to write auth.users in production -- that internal
-- mechanism is platform-managed and outside what these migrations control
-- or can observe.
CREATE SCHEMA IF NOT EXISTS auth;
GRANT ALL ON SCHEMA auth TO c2pro_owner;
GRANT USAGE ON SCHEMA auth TO authenticated;

SET ROLE c2pro_owner;

-- Matches the real enum from 20260113133853_init_schema.sql exactly --
-- handle_new_user() casts to it directly.
CREATE TYPE user_role AS ENUM ('owner', 'admin', 'member');

CREATE TABLE auth.users (
    id uuid PRIMARY KEY,
    email varchar(255),
    raw_user_meta_data jsonb
);

CREATE TABLE public.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text
);

CREATE TABLE public.users (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    email varchar(255),
    first_name varchar(100),
    last_name varchar(100),
    role user_role NOT NULL DEFAULT 'member',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

RESET ROLE;

-- Synthetic harness grant -- see the auth-schema comment above. Not a
-- reproduction of production's actual auth.users write path.
GRANT INSERT ON auth.users TO authenticated;
