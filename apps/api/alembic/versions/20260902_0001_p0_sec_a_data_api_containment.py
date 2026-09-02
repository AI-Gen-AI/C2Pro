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

# Default-ACL owners to close. `pg_default_acl` shows entries for both, but
# `postgres` is NOT a member of `supabase_admin`, so a bare
# ``ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin`` fails at deploy time with
# "must be member of role". Each target is therefore attempted only when the
# migration role can act for it, and skipped with a NOTICE otherwise.
# ``current_user`` is always included so the role actually creating tables is
# covered in every environment.
_DEFAULT_ACL_OWNERS = ("postgres", "supabase_admin")

REVOKE_EXISTING_TABLES_SQL = """
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM anon, authenticated, PUBLIC
"""

REVOKE_EXISTING_SEQUENCES_SQL = """
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM anon, authenticated, PUBLIC
"""

# NOTE: these DO blocks deliberately use quote_ident() + concatenation rather
# than format()/RAISE placeholders. A literal "%" in migration SQL is consumed
# by psycopg2's parameter interpolation when routed through op.execute(), so
# "%I" and "%" placeholders would break at deploy time while still passing a
# raw psql test. Keeping the SQL "%"-free makes it behave identically under
# psql and under Alembic.
DEFAULT_ACL_REVOKE_SQL = """
DO $$
DECLARE
    rec record;
BEGIN
    -- Driven from pg_default_acl rather than a hard-coded owner list: the set of
    -- roles holding default privileges in `public` is environment-specific
    -- (production shows `postgres` and `supabase_admin`), and a fixed list
    -- silently misses any other owner, leaving the recurrence engine running for
    -- it. Selecting only entries that actually grant to an external role keeps
    -- this the minimal delta.
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
                    ' IN SCHEMA public REVOKE ALL ON TABLES'
                    ' FROM anon, authenticated, PUBLIC';
        ELSE
            EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(rec.owner) ||
                    ' IN SCHEMA public REVOKE ALL ON SEQUENCES'
                    ' FROM anon, authenticated, PUBLIC';
        END IF;
    END LOOP;
END $$;
"""

# Emergency-only. Restores the exact pre-state captured read-only from the
# production project on 2026-09-02 and reproduced in
# apps/api/tests/security/fixtures/p0_sec_a_prestate.sql. Values are hard-coded
# rather than introspected so restoration is deterministic.
DEFAULT_ACL_RESTORE_SQL = """
DO $$
DECLARE
    target text;
    targets text[] := ARRAY['postgres', 'supabase_admin', current_user];
BEGIN
    FOREACH target IN ARRAY targets LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target) THEN
            CONTINUE;
        END IF;
        IF NOT pg_has_role(current_user, target, 'USAGE') THEN
            CONTINUE;
        END IF;
        EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(target) ||
                ' IN SCHEMA public GRANT ALL ON TABLES'
                ' TO anon, authenticated';
        EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || quote_ident(target) ||
                ' IN SCHEMA public GRANT ALL ON SEQUENCES'
                ' TO anon, authenticated';
    END LOOP;
END $$;
"""

RESTORE_EXISTING_TABLES_SQL = """
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    TO anon, authenticated
"""

RESTORE_EXISTING_SEQUENCES_SQL = """
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    TO anon, authenticated
"""


def upgrade() -> None:
    # 1. Remove the external Data API surface on existing objects.
    #    service_role is intentionally untouched: the waitlist route depends on it.
    op.execute(REVOKE_EXISTING_TABLES_SQL)
    op.execute(REVOKE_EXISTING_SEQUENCES_SQL)

    # 2. Drop the permissive checkpoint SELECT policies. With RLS still enabled
    #    and no policy left, these tables become deny-by-default externally while
    #    the backend (owner + BYPASSRLS) is unaffected.
    for table, policy in _CHECKPOINT_POLICIES:
        op.execute(
            f'DROP POLICY IF EXISTS "{policy}" ON public.{table}'
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

    op.execute(RESTORE_EXISTING_TABLES_SQL)
    op.execute(RESTORE_EXISTING_SEQUENCES_SQL)
