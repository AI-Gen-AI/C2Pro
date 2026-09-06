-- P0-SEC-D: close the one un-revoked SECURITY DEFINER EXECUTE grant.
--
-- WHAT THIS FIXES
-- ----------------
-- public.handle_new_user() is a SECURITY DEFINER trigger function (fires
-- AFTER INSERT ON auth.users, syncing the new Supabase Auth user into
-- public.users under whatever tenant_id its own metadata claims). Its owner
-- (the project's Postgres role) carries BYPASSRLS in production, so this
-- function's INSERT into public.users runs with RLS fully bypassed
-- regardless of the caller.
--
-- Every other SECURITY DEFINER function in this codebase (public.
-- create_tenant_and_owner, all 7 auth_bootstrap.* functions) explicitly
-- revokes PUBLIC/anon/authenticated immediately after creation.
-- handle_new_user() never did. Catalog inspection (pg_proc.proacl) on a
-- disposable database reproducing the production pg_default_acl posture
-- (ALTER DEFAULT PRIVILEGES ... IN SCHEMA public GRANT EXECUTE ON FUNCTIONS
-- TO anon, authenticated, service_role -- captured 2026-09-02, see
-- apps/api/tests/security/fixtures/p0_sec_a_prestate.sql) confirms this
-- function's real-world ACL grants EXECUTE to PUBLIC, anon, authenticated,
-- and service_role, none of it explicit or reviewed.
--
-- Direct invocation (`SELECT public.handle_new_user()`) is independently
-- blocked by PostgreSQL itself ("trigger functions can only be called as
-- triggers"), so this was not a reachable direct-call exploit. The gap is
-- the ACL itself: the only thing preventing broader reachability was an
-- incidental language restriction rather than a deliberate privilege
-- boundary, which is exactly the class of finding P0-SEC-D exists to close
-- before the non-BYPASSRLS application-role rollout. No sensitive
-- SECURITY DEFINER function should carry an unreviewed PUBLIC/anon/
-- authenticated/service_role grant, trigger-only or not.
--
-- WHY THIS IS SAFE
-- ----------------
-- Trigger invocation does not check the trigger function's EXECUTE ACL --
-- PostgreSQL fires BEFORE/AFTER triggers as part of the DML statement
-- itself, independent of whether the DML-performing role could call the
-- function directly. Revoking EXECUTE here does not change when or how the
-- Supabase Auth signup trigger (on_auth_user_created) fires. Verified
-- empirically on a disposable database: after this exact REVOKE, an
-- `authenticated`-role INSERT into auth.users still fires the trigger
-- correctly.
--
-- NO ALEMBIC COUNTERPART
-- -----------------------
-- public.handle_new_user() is Supabase Auth (GoTrue) integration glue --
-- it exists only because auth.users exists, and auth.users is a
-- Supabase-platform-managed table with no equivalent on the plain-Postgres
-- Alembic path. There is nothing to revoke there because the function
-- itself was never created there. This migration is Supabase-only by
-- necessity, not by omission.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public' AND p.proname = 'handle_new_user'
    ) THEN
        REVOKE ALL ON FUNCTION public.handle_new_user()
            FROM PUBLIC, anon, authenticated, service_role;
    END IF;
END $$;
