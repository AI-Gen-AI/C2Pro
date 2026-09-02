"""P0-SEC-A: contain external Supabase Data API access to the public schema.

Revision ID: 20260902_0001
Revises: 20260824_0001
Create Date: 2026-09-02

Audit record: blackboard/SESSION_2026-09-02_p0-sec-supabase-audit.md

WHAT THIS FIXES
---------------
A read-only audit of the production Supabase project established that the
`anon` and `authenticated` PostgREST roles held ALL privileges on every table
and sequence in `public`, and that this granted live anonymous read access to:

* the four LangGraph checkpoint tables (1,669 rows), whose RLS was enabled but
  whose only policy was ``FOR SELECT USING (true)``;
* `document_revisions` (8 rows / 3 tenants) through a fail-open
  ``COALESCE(..., tenant_id)`` policy that collapses to ``tenant_id = tenant_id``
  when no tenant context is set -- the normal state of a PostgREST request;
* the RLS-disabled evidence/reference tables and the `project_snapshots` leaf
  partitions, which PostgREST can address directly.

No breach is claimed: no access-log evidence of exploitation exists.

WHY REVOKE RATHER THAN WRITE POLICIES
-------------------------------------
A repository trace found no browser Supabase client, no `@supabase/supabase-js`
dependency and no `NEXT_PUBLIC_SUPABASE_*` usage. The only Data API caller is
`apps/web/app/api/waitlist/route.ts`, which is server-side and uses
`service_role`. FastAPI, Celery and the LangGraph checkpointer all connect
directly to PostgreSQL as the table owner, which additionally holds BYPASSRLS.

So `anon` and `authenticated` are unused by C2Pro, and removing their
privileges is the narrowest control that actually closes the surface. RLS is
retained as defence-in-depth, not as the sole control.

PORTABILITY
-----------
`anon`, `authenticated` and `service_role` are Supabase platform roles. They do
NOT exist on a plain PostgreSQL instance, which is what CI and local
development use, so every statement here is guarded on role existence. An
earlier revision of this migration named the roles literally and aborted the
whole chain with ``role "anon" does not exist``, taking every DB-backed CI lane
down with it.

The SQL is also deliberately free of ``%``: a literal percent sign is consumed
by psycopg2 parameter interpolation under ``op.execute()``, so ``format('%I')``
and ``RAISE NOTICE '%'`` would behave differently under Alembic than under a
raw psql test. Identifiers are quoted with ``quote_ident()`` and concatenated.

SCOPE DISCIPLINE
----------------
Deliberately NOT changed here (each belongs to a later phase):
fail-open ``COALESCE`` policy bodies (P0-SEC-B), the `app.current_tenant` /
`app.current_tenant_id` split (P0-SEC-B), function EXECUTE grants, SECURITY
DEFINER functions and function search_path (P0-SEC-D), extension schemas
(P1-SEC-E), Supabase Auth, the `waitlist_signups` deny-all policy state,
FORCE RLS, and database roles.

`service_role` privileges are preserved everywhere so the waitlist route keeps
working.
"""

from __future__ import annotations

from alembic import op

revision = "20260902_0001"
down_revision = "20260824_0001"
branch_labels = None
depends_on = None


# Tables whose RLS is turned on here. They get no policies in this migration:
# with the Data API grants revoked, RLS-on-with-no-policy is deny-by-default for
# every non-BYPASSRLS role, which is the intended end state. Inventing tenant
# policies for them is P0-SEC-B work, and `category_centroids` is global
# reference data that must NOT be given manufactured tenant semantics.
_RLS_ENABLE_TABLES = (
    "evidence_claims",
    "evidence_extraction_events",
    "category_centroids",
    "project_snapshots_2026_06",
    "project_snapshots_2026_07",
    "project_snapshots_2026_08",
    "project_snapshots_default",
)

# The permissive policies added by 20260403_0003 to clear the
# `rls_disabled_in_public` advisor ERROR. LangGraph does not require them.
_CHECKPOINT_POLICIES = (
    ("checkpoints", "checkpoints_select"),
    ("checkpoint_blobs", "checkpoint_blobs_select"),
    ("checkpoint_writes", "checkpoint_writes_select"),
    ("checkpoint_migrations", "checkpoint_migrations_select"),
)

# Builds a comma-separated grantee list containing only the external Supabase
# roles that actually exist, always ending in PUBLIC (a keyword, never quoted).
# On a plain PostgreSQL instance this collapses to just PUBLIC.
_EXTERNAL_ROLE_LIST = """
    SELECT concat_ws(', ',
               (SELECT string_agg(quote_ident(r.name), ', ' ORDER BY r.name)
                  FROM unnest(ARRAY['anon', 'authenticated']) AS r(name)
                 WHERE EXISTS (SELECT 1 FROM pg_roles g WHERE g.rolname = r.name)),
               'PUBLIC')
"""

REVOKE_EXISTING_SQL = f"""
DO $$
DECLARE
    grantees text;
BEGIN
    {_EXTERNAL_ROLE_LIST} INTO grantees;

    EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM ' || grantees;
    EXECUTE 'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM ' || grantees;
END $$;
"""

# Driven from pg_default_acl rather than a hard-coded owner list: the set of
# roles holding default privileges in `public` is environment-specific
# (production shows `postgres` and `supabase_admin`), and a fixed list silently
# misses any other owner, leaving the recurrence engine running for it.
# Selecting only entries that actually grant to an external role keeps this the
# minimal delta.
#
# `postgres` is NOT a member of `supabase_admin`, so an unguarded
# ``ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin`` fails at deploy with
# "must be member of role". Each owner is therefore attempted only when the
# migration role can act for it, and skipped with a NOTICE otherwise.
DEFAULT_ACL_REVOKE_SQL = f"""
DO $$
DECLARE
    rec record;
    grantees text;
BEGIN
    {_EXTERNAL_ROLE_LIST} INTO grantees;

    FOR rec IN
        SELECT DISTINCT pg_get_userbyid(d.defaclrole) AS owner, d.defaclobjtype AS objtype
          FROM pg_default_acl d
          JOIN pg_namespace n ON n.oid = d.defaclnamespace
         WHERE n.nspname = 'public'
           AND d.defaclobjtype IN ('r', 'S')
           AND EXISTS (
               SELECT 1 FROM aclexplode(d.defaclacl) a
                WHERE a.grantee = 0
                   OR pg_get_userbyid(a.grantee) IN ('anon', 'authenticated')
           )
    LOOP
        IF NOT pg_has_role(current_user, rec.owner, 'USAGE') THEN
            RAISE NOTICE USING MESSAGE =
                'P0-SEC-A: skipped default privileges for role ' || rec.owner ||
                ' (migration role is not a member). Close it at platform level.';
            CONTINUE;
        END IF;
        IF rec.objtype = 'r' THEN
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public REVOKE ALL ON TABLES FROM ' || grantees;
        ELSE
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public REVOKE ALL ON SEQUENCES FROM ' || grantees;
        END IF;
    END LOOP;
END $$;
"""

# Emergency-only. Restores the exact pre-state captured read-only from the
# production project on 2026-09-02 and reproduced in
# apps/api/tests/security/fixtures/p0_sec_a_prestate.sql. The grantee set is
# hard-coded rather than introspected so restoration is deterministic; only the
# existence guard is dynamic, because the roles are absent outside Supabase.
DEFAULT_ACL_RESTORE_SQL = """
DO $$
DECLARE
    rec record;
    grantees text;
BEGIN
    SELECT string_agg(quote_ident(r.name), ', ' ORDER BY r.name) INTO grantees
      FROM unnest(ARRAY['anon', 'authenticated']) AS r(name)
     WHERE EXISTS (SELECT 1 FROM pg_roles g WHERE g.rolname = r.name);

    IF grantees IS NULL THEN
        RETURN;
    END IF;

    FOR rec IN
        SELECT DISTINCT pg_get_userbyid(d.defaclrole) AS owner, d.defaclobjtype AS objtype
          FROM pg_default_acl d
          JOIN pg_namespace n ON n.oid = d.defaclnamespace
         WHERE n.nspname = 'public' AND d.defaclobjtype IN ('r', 'S')
    LOOP
        IF NOT pg_has_role(current_user, rec.owner, 'USAGE') THEN
            CONTINUE;
        END IF;
        IF rec.objtype = 'r' THEN
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public GRANT ALL ON TABLES TO ' || grantees;
        ELSE
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public GRANT ALL ON SEQUENCES TO ' || grantees;
        END IF;
    END LOOP;
END $$;
"""

RESTORE_EXISTING_SQL = """
DO $$
DECLARE
    grantees text;
BEGIN
    SELECT string_agg(quote_ident(r.name), ', ' ORDER BY r.name) INTO grantees
      FROM unnest(ARRAY['anon', 'authenticated']) AS r(name)
     WHERE EXISTS (SELECT 1 FROM pg_roles g WHERE g.rolname = r.name);

    IF grantees IS NULL THEN
        RETURN;
    END IF;

    EXECUTE 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ' || grantees;
    EXECUTE 'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ' || grantees;
END $$;
"""


def upgrade() -> None:
    # 1. Remove the external Data API surface on existing objects.
    #    service_role is intentionally untouched: the waitlist route depends on it.
    op.execute(REVOKE_EXISTING_SQL)

    # 2. Drop the permissive checkpoint SELECT policies. With RLS still enabled
    #    and no policy left, these tables become deny-by-default externally while
    #    the backend (owner + BYPASSRLS) is unaffected.
    for table, policy in _CHECKPOINT_POLICIES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'DROP POLICY IF EXISTS "{policy}" ON public.{table}';
                END IF;
            END $$;
            """
        )

    # 3. Enable RLS where it was missing entirely, including every snapshot leaf.
    #    Leaves deliberately receive no policies: copying the parent's fail-open
    #    policy down would reproduce the very defect P0-SEC-B exists to remove.
    for table in _RLS_ENABLE_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;
            """
        )

    # 4. Close the recurrence engine so the next CREATE TABLE does not re-open
    #    everything this migration just closed. Functions are out of scope.
    op.execute(DEFAULT_ACL_REVOKE_SQL)


def downgrade() -> None:
    """Restore the pre-P0-SEC-A state.

    WARNING: this deliberately restores a KNOWN-INSECURE configuration in which
    `anon` and `authenticated` regain full privileges on every table and
    sequence in `public`, and the LangGraph checkpoint tables become anonymously
    readable again. It exists for disposable-environment testing and emergency
    rollback only. Do not run it to "unblock" anything.
    """
    op.execute(DEFAULT_ACL_RESTORE_SQL)

    for table in _RLS_ENABLE_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY';
                END IF;
            END $$;
            """
        )

    for table, policy in _CHECKPOINT_POLICIES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'CREATE POLICY "{policy}" ON public.{table} '
                            'FOR SELECT USING (true)';
                END IF;
            END $$;
            """
        )

    op.execute(RESTORE_EXISTING_SQL)
