"""C1 (Option-C runtime RLS completeness): fix wrong tenant GUC name on 4 tables.

Revision ID: 20260906_0002
Revises: 20260905_0001
Create Date: 2026-09-06

WHAT THIS FIXES
---------------
Four Alembic-created tables carry RLS policies that reference a GUC named
``app.current_tenant_id`` (note the extra ``_id``):

  - dlq_failed_tasks           (20260405_0002_create_dlq_failed_tasks_table.py)
  - wbs_nodes                  (20260406_0001_add_wbs_nodes_table.py)
  - notification_configs       (20260406_0003_add_notification_configs_table.py)
  - disclaimer_acceptances     (20260807_0001_add_disclaimer_acceptances.py)

The application never sets that GUC. ``src/core/database.py`` only ever sets
and reads ``app.current_tenant`` (via ``SET SESSION app.current_tenant = ''``
on connect and ``SET LOCAL app.current_tenant = '<uuid>'`` per request/task).
Under real RLS enforcement (no table ownership / BYPASSRLS masking it), these
four tables are permanently deny-all for every tenant, not merely for the
wrong one -- a functional break, not a data leak. Today this is invisible
because the shared runtime role owns every table and table ownership bypasses
RLS independently of the BYPASSRLS attribute.

The Supabase CLI mirror migrations for three of these four tables
(20260405000200_add_dlq_failed_tasks.sql, 20260406000100_add_wbs_nodes_and_
configs.sql) already use the correct ``app.current_tenant`` GUC with the
canonical NULLIF fail-closed predicate and per-command policies -- only the
Alembic path drifted. There is no Supabase CLI mirror for
disclaimer_acceptances (Alembic-only table); its fix is written directly here
using the same canonical predicate P0-SEC-B established.

notification_configs' pre-fix policy is strictly worse than the other three:
it omits the ``true`` (missing_ok) second argument to ``current_setting``, so
a session where ``app.current_tenant_id`` was never defined at all raises a
hard "unrecognized configuration parameter" error rather than failing closed.

SCOPE DISCIPLINE (Option C1 authorization)
-------------------------------------------
Per-table policy *commands* are the narrowest set the live call graph proves
is needed today, NOT copied wholesale from the (more permissive) Supabase
mirror:

  - dlq_failed_tasks:       SELECT, INSERT, UPDATE   (no DELETE -- none found
                            in src/core/dlq/dlq_service.py; the Supabase
                            mirror's DELETE policy on this table has no
                            corresponding live caller either and is a
                            pre-existing discrepancy this migration does not
                            resolve)
  - wbs_nodes:              SELECT, INSERT, UPDATE, DELETE (DELETE confirmed
                            live: wbs/adapters/persistence/wbs_node_repository
                            .py's delete() issues real session.delete() calls
                            via DeleteWBSNodeUseCase)
  - notification_configs:   SELECT, INSERT, UPDATE   (no DELETE found in
                            notification_config_repository.py)
  - disclaimer_acceptances: SELECT, INSERT            (unchanged from the
                            pre-fix command shape -- only the predicate is
                            wrong; repository.py never issues UPDATE/DELETE)

NOT IN THIS MIGRATION
----------------------
  - No c2pro_app role is created and no GRANTs are issued. PostgreSQL
    policies apply to every non-owning, non-BYPASSRLS role by default; the
    base table-level GRANTs and the role itself are C3 cutover work.
  - dlq_failed_tasks also has a deliberate cross-tenant PLATFORM-ADMIN read/
    retry surface (src/admin/adapters/http/router.py, gated by
    UserRole.ADMIN, using get_raw_session() with no tenant GUC at all --
    "List DLQ entries across tenants" per that file's own docstring). No
    policy here accommodates it: doing so would require a new session-level
    signal (e.g. a distinct GUC set only by the trusted admin code path)
    that does not exist today, and inventing one is an architecture decision
    reserved for MASTER, not a mechanical policy fix. This surface will not
    function once c2pro_app is the runtime role unless/until that decision is
    made; it is unaffected while the shared owning/BYPASSRLS role remains in
    use, which C1 does not change.
  - category_centroids and the evidence_* tables need no grant for c2pro_app
    at all (see C1 return report): category_centroids' only write path is an
    offline admin script, not live runtime traffic; the evidence_* tables'
    only repository is unwired dead code.
  - review_items already carries the correct canonical per-command policies
    (tenant_isolation_select/insert/update using app.current_tenant with
    NULLIF) -- no change needed.

PORTABILITY
-----------
No Supabase-platform roles referenced. Runs unchanged on plain PostgreSQL.
"""

from __future__ import annotations

from alembic import op

revision = "20260906_0002"
down_revision = "20260905_0001"
branch_labels = None
depends_on = None

_FAIL_CLOSED = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"

# Pre-fix (broken) predicate variants, needed only by downgrade() to restore
# the exact prior bytes. notification_configs omits the missing_ok arg.
_BROKEN_WITH_MISSING_OK = "tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid"
_BROKEN_NO_MISSING_OK = "tenant_id = current_setting('app.current_tenant_id')::uuid"


def upgrade() -> None:
    """Replace 4 broken-GUC policies with canonical per-command NULLIF policies."""

    # ── wbs_nodes: consistency precondition ──────────────────────────────────
    # wbs_nodes carries project_id NOT NULL; verify tenant_id agrees with the
    # owning project's tenant_id before any row could become newly reachable
    # under a correct tenant match. (dlq_failed_tasks/notification_configs
    # have no project_id column; disclaimer_acceptances' project_id is a
    # free-form string, not a projects.id FK -- neither check applies there.)
    op.execute(
        """
        DO $c1_wbs_pre$
        DECLARE
            v_bad bigint;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = 'projects'
            ) OR NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = 'wbs_nodes'
            ) THEN
                RETURN;
            END IF;

            SELECT COUNT(*) INTO v_bad
              FROM public.wbs_nodes w
              JOIN public.projects p ON p.id = w.project_id
             WHERE w.tenant_id IS DISTINCT FROM p.tenant_id;
            IF v_bad > 0 THEN
                RAISE EXCEPTION USING MESSAGE =
                    'C1 PRECONDITION FAILED: wbs_nodes has ' || v_bad::text ||
                    ' row(s) where tenant_id IS DISTINCT FROM projects.tenant_id.'
                    ' Inspect and reconcile before re-running this migration.';
            END IF;

            SELECT COUNT(*) INTO v_bad
              FROM public.wbs_nodes w
             WHERE w.project_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM public.projects p WHERE p.id = w.project_id);
            IF v_bad > 0 THEN
                RAISE EXCEPTION USING MESSAGE =
                    'C1 PRECONDITION FAILED: wbs_nodes has ' || v_bad::text ||
                    ' orphaned project_id(s) with no matching projects row.'
                    ' Inspect and reconcile before re-running this migration.';
            END IF;
        END $c1_wbs_pre$;
        """
    )

    # ── dlq_failed_tasks: FOR ALL -> SELECT/INSERT/UPDATE ────────────────────
    op.execute("DROP POLICY IF EXISTS dlq_tenant_isolation ON dlq_failed_tasks")
    op.execute(
        f"CREATE POLICY dlq_tenant_isolation_select ON dlq_failed_tasks "
        f"FOR SELECT USING ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY dlq_tenant_isolation_insert ON dlq_failed_tasks "
        f"FOR INSERT WITH CHECK ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY dlq_tenant_isolation_update ON dlq_failed_tasks "
        f"FOR UPDATE USING ({_FAIL_CLOSED})"
    )

    # ── wbs_nodes: FOR ALL -> SELECT/INSERT/UPDATE/DELETE ────────────────────
    op.execute("DROP POLICY IF EXISTS wbs_nodes_tenant_isolation ON wbs_nodes")
    op.execute(
        f"CREATE POLICY wbs_nodes_tenant_isolation_select ON wbs_nodes "
        f"FOR SELECT USING ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY wbs_nodes_tenant_isolation_insert ON wbs_nodes "
        f"FOR INSERT WITH CHECK ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY wbs_nodes_tenant_isolation_update ON wbs_nodes "
        f"FOR UPDATE USING ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY wbs_nodes_tenant_isolation_delete ON wbs_nodes "
        f"FOR DELETE USING ({_FAIL_CLOSED})"
    )

    # ── notification_configs: FOR ALL -> SELECT/INSERT/UPDATE ────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notification_configs")
    op.execute(
        f"CREATE POLICY notification_configs_tenant_isolation_select ON notification_configs "
        f"FOR SELECT USING ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY notification_configs_tenant_isolation_insert ON notification_configs "
        f"FOR INSERT WITH CHECK ({_FAIL_CLOSED})"
    )
    op.execute(
        f"CREATE POLICY notification_configs_tenant_isolation_update ON notification_configs "
        f"FOR UPDATE USING ({_FAIL_CLOSED})"
    )

    # ── disclaimer_acceptances: fix predicate only (command shape unchanged) ─
    op.execute("DROP POLICY IF EXISTS disclaimer_tenant_isolation_select ON disclaimer_acceptances")
    op.execute(
        f"CREATE POLICY disclaimer_tenant_isolation_select ON disclaimer_acceptances "
        f"FOR SELECT USING ({_FAIL_CLOSED})"
    )
    op.execute("DROP POLICY IF EXISTS disclaimer_tenant_isolation_insert ON disclaimer_acceptances")
    op.execute(
        f"CREATE POLICY disclaimer_tenant_isolation_insert ON disclaimer_acceptances "
        f"FOR INSERT WITH CHECK ({_FAIL_CLOSED})"
    )


def downgrade() -> None:
    """Restore the pre-C1 broken-GUC policies verbatim (KNOWN-BROKEN).

    This does not restore an insecure state (the pre-fix state was already
    deny-all for everyone, never a leak) -- it restores a deny-all-for-
    everyone-including-the-correct-tenant state. Only execute with explicit
    MASTER incident authorisation.
    """
    op.execute("DROP POLICY IF EXISTS dlq_tenant_isolation_select ON dlq_failed_tasks")
    op.execute("DROP POLICY IF EXISTS dlq_tenant_isolation_insert ON dlq_failed_tasks")
    op.execute("DROP POLICY IF EXISTS dlq_tenant_isolation_update ON dlq_failed_tasks")
    op.execute(
        f"CREATE POLICY dlq_tenant_isolation ON dlq_failed_tasks "
        f"FOR ALL USING ({_BROKEN_WITH_MISSING_OK})"
    )

    op.execute("DROP POLICY IF EXISTS wbs_nodes_tenant_isolation_select ON wbs_nodes")
    op.execute("DROP POLICY IF EXISTS wbs_nodes_tenant_isolation_insert ON wbs_nodes")
    op.execute("DROP POLICY IF EXISTS wbs_nodes_tenant_isolation_update ON wbs_nodes")
    op.execute("DROP POLICY IF EXISTS wbs_nodes_tenant_isolation_delete ON wbs_nodes")
    op.execute(
        f"CREATE POLICY wbs_nodes_tenant_isolation ON wbs_nodes "
        f"FOR ALL USING ({_BROKEN_WITH_MISSING_OK})"
    )

    op.execute("DROP POLICY IF EXISTS notification_configs_tenant_isolation_select ON notification_configs")
    op.execute("DROP POLICY IF EXISTS notification_configs_tenant_isolation_insert ON notification_configs")
    op.execute("DROP POLICY IF EXISTS notification_configs_tenant_isolation_update ON notification_configs")
    op.execute(
        f"CREATE POLICY tenant_isolation ON notification_configs "
        f"FOR ALL USING ({_BROKEN_NO_MISSING_OK})"
    )

    op.execute("DROP POLICY IF EXISTS disclaimer_tenant_isolation_select ON disclaimer_acceptances")
    op.execute(
        f"CREATE POLICY disclaimer_tenant_isolation_select ON disclaimer_acceptances "
        f"FOR SELECT USING ({_BROKEN_WITH_MISSING_OK})"
    )
    op.execute("DROP POLICY IF EXISTS disclaimer_tenant_isolation_insert ON disclaimer_acceptances")
    op.execute(
        f"CREATE POLICY disclaimer_tenant_isolation_insert ON disclaimer_acceptances "
        f"FOR INSERT WITH CHECK ({_BROKEN_WITH_MISSING_OK})"
    )
