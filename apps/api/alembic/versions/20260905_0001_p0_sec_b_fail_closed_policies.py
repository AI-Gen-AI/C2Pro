"""P0-SEC-B: replace 24 fail-open COALESCE RLS policies with fail-closed NULLIF.

Revision ID: 20260905_0001
Revises: 20260902_0001
Create Date: 2026-09-05

WHAT THIS FIXES
---------------
Six tables created by the June 2026 V3 migration chain carry RLS policies of
the form:

    tenant_id = COALESCE(
        NULLIF(current_setting('app.current_tenant', true), '')::uuid,
        tenant_id
    )

When ``app.current_tenant`` is absent or set to an empty string, COALESCE
falls back to the row's own ``tenant_id``, reducing the expression to
``tenant_id = tenant_id`` (always TRUE).  Any connection without a tenant GUC
can read or write every row in these tables — a fail-open policy.

Four other tables (analyses, alerts, coherence_results, clause_embeddings)
carry both canonical per-operation NULLIF CRUD policies AND leftover FOR ALL
PERMISSIVE policies from an earlier RLS pass.  Multiple PERMISSIVE policies
are OR-combined by PostgreSQL, so the excess FOR ALL policies widen the
effective access beyond what the CRUD policies alone would allow.

This migration:

  Part A — CONSISTENCY PRECONDITION
    For each of the four excess-policy tables that also carry a project_id,
    asserts that every row's tenant_id matches its project's tenant_id.
    If any mismatch exists, the transaction is ABORTED.
    Silent data repair is NOT performed here.

  Part B — 24 COALESCE → NULLIF REPLACEMENTS (6 tables × 4 policies)
    Each COALESCE expression is replaced with:

        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid

    Under this form, an absent or empty GUC produces NULL, which never equals
    any tenant_id, so uncontexted connections see and can write nothing.

  Part C — 5 EXCESS PERMISSIVE POLICY DROPS (4 tables)
    Drops the leftover FOR ALL policies so that the canonical per-operation
    CRUD policies are the sole RLS policies on those tables.

PORTABILITY
-----------
No Supabase-platform roles are referenced.  No ``%`` signs.  The migration
runs unchanged on plain PostgreSQL (CI and local dev).

TRIGGER INTERACTIONS
--------------------
``project_events`` carries a BEFORE UPDATE OR DELETE trigger that raises an
exception before any row reaches RLS evaluation.  The UPDATE and DELETE
policies on that table are unreachable at runtime but are corrected here for
structural completeness and future-proofing (e.g. Option-C role work, policy
audits).  The same reasoning applies to ``project_snapshots``' BEFORE UPDATE
trigger.

SCOPE DISCIPLINE
----------------
Not changed here (each belongs to a later authorised slice):
  - project_snapshots partition children (P0-SEC-A already enabled RLS;
    children inherit parent policies — no independent action needed here)
  - Function EXECUTE grants, SECURITY DEFINER, mutable search_path (P0-SEC-D)
  - Non-BYPASSRLS HTTP application role (Option C, requires this migration
    as a prerequisite — do not bundle)
  - ``alembic_version_select USING (true)`` (separate cleanup item)
  - ``supabase_admin`` PUBLIC default ACL (platform residual)
"""

from __future__ import annotations

from alembic import op

revision = "20260905_0001"
down_revision = "20260902_0001"
branch_labels = None
depends_on = None

# ── Policy expressions ──────────────────────────────────────────────────────

_FAIL_OPEN = (
    "tenant_id = COALESCE("
    "NULLIF(current_setting('app.current_tenant', true), '')::uuid, "
    "tenant_id)"
)
_FAIL_CLOSED = (
    "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"
)

# ── Table / policy registry ─────────────────────────────────────────────────

# Each entry: (table, select_policy, insert_policy, update_policy, delete_policy)
# 6 tables × 4 policies = 24 semantic operations.
_COALESCE_TABLES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "project_states",
        "project_states_select",
        "project_states_insert",
        "project_states_update",
        "project_states_delete",
    ),
    (
        "project_state_entities",
        "pse_select",
        "pse_insert",
        "pse_update",
        "pse_delete",
    ),
    (
        "document_revisions",
        "docrev_select",
        "docrev_insert",
        "docrev_update",
        "docrev_delete",
    ),
    (
        "project_events",
        "project_events_select",
        "project_events_insert",
        "project_events_update",
        "project_events_delete",
    ),
    (
        "project_snapshots",
        "project_snapshots_select",
        "project_snapshots_insert",
        "project_snapshots_update",
        "project_snapshots_delete",
    ),
    (
        "document_artifacts",
        "document_artifacts_select",
        "document_artifacts_insert",
        "document_artifacts_update",
        "document_artifacts_delete",
    ),
)

# 5 excess FOR ALL permissive policies: (table, policy_name)
_EXCESS_POLICIES: tuple[tuple[str, str], ...] = (
    ("analyses",          "tenant_isolation_analyses"),
    ("alerts",            "tenant_isolation_alerts"),
    ("coherence_results", "tenant_isolation_coherence_results"),
    ("clause_embeddings", "tenant_isolation_clause_embeddings"),
    ("clause_embeddings", "clause_embeddings_tenant_isolation"),
)

# Tables for which a project-ownership consistency check is mandatory.
_PRECONDITION_TABLES = (
    "analyses",
    "alerts",
    "coherence_results",
    "clause_embeddings",
)


def upgrade() -> None:
    """Fail-close 24 policies; drop 5 excess permissive policies.

    Part A: consistency precondition.
    Part B: 24 COALESCE -> NULLIF replacements.
    Part C: 5 excess permissive policy drops.
    """

    # ── Part A: consistency precondition ─────────────────────────────────────
    # Constructs a comma-separated literal for use inside the PL/pgSQL ARRAY[].
    table_list = ", ".join(f"'{t}'" for t in _PRECONDITION_TABLES)

    op.execute(
        f"""
        DO $p0secb_pre$
        DECLARE
            v_bad   bigint;
            v_table text;
        BEGIN
            -- If projects table is absent (non-production environment without
            -- the full schema), skip the check — no mismatches can exist.
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = 'projects'
            ) THEN
                RETURN;
            END IF;

            FOREACH v_table IN ARRAY ARRAY[{table_list}]
            LOOP
                -- tenant_id vs project.tenant_id mismatch check
                EXECUTE format(
                    'SELECT COUNT(*) FROM public.%%I t
                       JOIN public.projects p ON p.id = t.project_id
                      WHERE t.tenant_id IS DISTINCT FROM p.tenant_id',
                    v_table
                ) INTO v_bad;
                IF v_bad > 0 THEN
                    RAISE EXCEPTION
                        'P0-SEC-B PRECONDITION FAILED: table %% has %% row(s) where '
                        'tenant_id IS DISTINCT FROM projects.tenant_id. '
                        'Inspect and reconcile before re-running this migration.',
                        v_table, v_bad;
                END IF;

                -- orphaned project_id check
                EXECUTE format(
                    'SELECT COUNT(*) FROM public.%%I t
                      WHERE t.project_id IS NOT NULL
                        AND NOT EXISTS (
                            SELECT 1 FROM public.projects p WHERE p.id = t.project_id
                        )',
                    v_table
                ) INTO v_bad;
                IF v_bad > 0 THEN
                    RAISE EXCEPTION
                        'P0-SEC-B PRECONDITION FAILED: table %% has %% orphaned '
                        'project_id(s) with no matching projects row. '
                        'Inspect and reconcile before re-running this migration.',
                        v_table, v_bad;
                END IF;
            END LOOP;
        END $p0secb_pre$;
        """
    )

    # ── Part B: 24 COALESCE -> NULLIF replacements ───────────────────────────
    op.execute("SET LOCAL lock_timeout = '30s'")
    for table, sel, ins, upd, dlt in _COALESCE_TABLES:
        # SELECT
        op.execute(f"DROP POLICY IF EXISTS {sel} ON {table}")
        op.execute(
            f"CREATE POLICY {sel} ON {table} FOR SELECT USING ({_FAIL_CLOSED})"
        )
        # INSERT  (WITH CHECK — INSERT has no USING clause)
        op.execute(f"DROP POLICY IF EXISTS {ins} ON {table}")
        op.execute(
            f"CREATE POLICY {ins} ON {table} FOR INSERT WITH CHECK ({_FAIL_CLOSED})"
        )
        # UPDATE
        op.execute(f"DROP POLICY IF EXISTS {upd} ON {table}")
        op.execute(
            f"CREATE POLICY {upd} ON {table} FOR UPDATE USING ({_FAIL_CLOSED})"
        )
        # DELETE
        op.execute(f"DROP POLICY IF EXISTS {dlt} ON {table}")
        op.execute(
            f"CREATE POLICY {dlt} ON {table} FOR DELETE USING ({_FAIL_CLOSED})"
        )

    # ── Part C: 5 excess permissive policy drops ─────────────────────────────
    for table, policy in _EXCESS_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")


def downgrade() -> None:
    """Restore the pre-P0-SEC-B insecure state.

    KNOWN-INSECURE: this downgrade deliberately restores the COALESCE fail-open
    policies and the 5 excess permissive FOR ALL policies.  It exists so that a
    failed upgrade or a pre-production rollback can reach a deterministic known
    state without data loss.  It does NOT make the system safe.

    Only execute this with explicit MASTER incident authorisation.
    """
    # Restore 5 excess FOR ALL policies (using NULLIF — their original form
    # from 20260403_0002 / 20260421_0001, not the fail-open COALESCE).
    for table, policy in _EXCESS_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(
            f"CREATE POLICY {policy} ON {table} FOR ALL USING ({_FAIL_CLOSED})"
        )

    # Restore 24 COALESCE policies (fail-open — the deliberately insecure prior
    # state required to make downgrade honest about what it reinstates).
    for table, sel, ins, upd, dlt in _COALESCE_TABLES:
        # DELETE
        op.execute(f"DROP POLICY IF EXISTS {dlt} ON {table}")
        op.execute(
            f"CREATE POLICY {dlt} ON {table} FOR DELETE USING ({_FAIL_OPEN})"
        )
        # UPDATE
        op.execute(f"DROP POLICY IF EXISTS {upd} ON {table}")
        op.execute(
            f"CREATE POLICY {upd} ON {table} FOR UPDATE USING ({_FAIL_OPEN})"
        )
        # INSERT
        op.execute(f"DROP POLICY IF EXISTS {ins} ON {table}")
        op.execute(
            f"CREATE POLICY {ins} ON {table} FOR INSERT WITH CHECK ({_FAIL_OPEN})"
        )
        # SELECT
        op.execute(f"DROP POLICY IF EXISTS {sel} ON {table}")
        op.execute(
            f"CREATE POLICY {sel} ON {table} FOR SELECT USING ({_FAIL_OPEN})"
        )
