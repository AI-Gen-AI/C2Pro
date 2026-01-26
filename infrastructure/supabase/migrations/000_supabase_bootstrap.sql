-- =====================================================
-- C2Pro - Supabase Auth Bootstrap (Test/Local)
-- =====================================================
-- Purpose:
--   Provide a minimal auth schema/functions when running
--   migrations against a non-Supabase Postgres database.
--   This avoids hard failures in RLS policies and triggers.
--
-- Notes:
--   - If Supabase Auth already exists, this is a no-op.
--   - Do NOT override existing Supabase functions.
-- =====================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'auth') THEN
        CREATE SCHEMA auth;
    END IF;
END $$;

-- Minimal auth.users table for trigger compatibility.
CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY,
    email VARCHAR(255),
    raw_user_meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- auth.uid(): returns user id from request.jwt.claim.sub when present.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth' AND p.proname = 'uid' AND p.pronargs = 0
    ) THEN
        CREATE FUNCTION auth.uid() RETURNS uuid
        LANGUAGE sql STABLE
        AS $fn$
            SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid;
        $fn$;
    END IF;
END $$;

-- auth.role(): returns role from request.jwt.claim.role when present.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth' AND p.proname = 'role' AND p.pronargs = 0
    ) THEN
        CREATE FUNCTION auth.role() RETURNS text
        LANGUAGE sql STABLE
        AS $fn$
            SELECT NULLIF(current_setting('request.jwt.claim.role', true), '');
        $fn$;
    END IF;
END $$;

-- auth.jwt(): returns jwt claims as jsonb when present.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth' AND p.proname = 'jwt' AND p.pronargs = 0
    ) THEN
        CREATE FUNCTION auth.jwt() RETURNS jsonb
        LANGUAGE sql STABLE
        AS $fn$
            SELECT COALESCE(
                NULLIF(current_setting('request.jwt.claims', true), '')::jsonb,
                '{}'::jsonb
            );
        $fn$;
    END IF;
END $$;
