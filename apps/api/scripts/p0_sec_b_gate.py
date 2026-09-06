#!/usr/bin/env python3
"""Self-verifying gate for the P0-SEC-B fail-closed RLS migration.

Builds a disposable database that reproduces the COALESCE fail-open state for
all 6 affected tables, then proves the full lifecycle:

    pre-state (COALESCE)  →  TRUE RED   (GUC absent / GUC='' sees all rows)
    upgrade (NULLIF)       →  GREEN      (GUC absent / GUC='' sees no rows)
    downgrade              →  TRUE RED   (rollback is honest)
    upgrade (re-apply)     →  GREEN      (idempotent)

Additionally asserts:
    BEHAVIORAL INVARIANTS hold before AND after the migration:
      - wrong-tenant GUC   → only wrong-tenant rows visible (already closed)
      - correct-tenant GUC → only correct-tenant rows visible
    PRECONDITION ABORT:
      Injecting a mismatched tenant_id row causes the upgrade to raise
      "P0-SEC-B PRECONDITION FAILED" and leave the database unchanged.

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres \\
        python apps/api/scripts/p0_sec_b_gate.py

DSN is read exclusively from P0_SEC_ADMIN_DSN and must resolve to a loopback
host (localhost / 127.0.0.1 / ::1). Remote or cloud hosts are rejected at
startup.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p0_sec_b_common import REPO_ROOT, emitted_sql  # noqa: E402
from security_gate_common import exec_sql as _exec_script  # noqa: E402
from security_gate_common import pg_connection as _connection  # noqa: E402
from security_gate_common import resolve_admin_dsn as _resolve_admin_dsn_impl  # noqa: E402

FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_b_prestate.sql"
DB_NAME = "p0_sec_b_gate"

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-000000000002"
PROJECT_A = "cccccccc-cccc-cccc-cccc-000000000001"

_COALESCE_TABLES = (
    "project_states",
    "project_state_entities",
    "document_revisions",
    "project_events",
    "project_snapshots",
    "document_artifacts",
)


def _resolve_admin_dsn() -> str:
    return _resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")


def _exec_script_expect_error(dsn: str, sql: str, expected_fragment: str) -> None:
    """Execute SQL and assert it raises an exception containing expected_fragment."""
    try:
        try:
            import psycopg

            with psycopg.connect(dsn, autocommit=True) as conn:
                conn.execute(sql)
        except ImportError:
            import psycopg2

            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
            finally:
                conn.close()
    except SystemExit:
        raise
    except Exception as exc:
        msg = str(exc)
        if expected_fragment not in msg:
            raise SystemExit(f"GATE FAILED: expected '{expected_fragment}' in error, got: {msg}")
        return
    raise SystemExit(
        f"GATE FAILED: expected exception containing '{expected_fragment}' but SQL succeeded"
    )


def _count_rows_as_role(
    dsn: str,
    table: str,
    *,
    tenant_guc: str | None,
) -> int:
    """Count rows in table as c2pro_sec_rls_test with an optional GUC.

    SET ROLE switches effective user to a NOSUPERUSER NOBYPASSRLS role so RLS
    is enforced.  The GUC is SET/RESET within the same autocommit session so it
    affects only this call.

    set_config() is used instead of "SET app.current_tenant = %s" because
    PostgreSQL's SET command does not accept parameterised placeholders ($1).
    is_local=false sets it at session scope so the subsequent SELECT sees it.
    """
    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute("RESET app.current_tenant")
        if tenant_guc is not None:
            cur.execute("SELECT set_config('app.current_tenant', %s, false)", (tenant_guc,))
        cur.execute("SET ROLE c2pro_sec_rls_test")
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608 — table is hardcoded
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")


def _assert_single_table_phase(
    dsn: str,
    table: str,
    label: str,
    *,
    expect_fail_open: bool,
) -> None:
    """Check one table for the expected fail-open/fail-closed behaviour."""
    for tenant_guc in (None, ""):
        guc_label = "GUC absent" if tenant_guc is None else "GUC=''"
        count = _count_rows_as_role(dsn, table, tenant_guc=tenant_guc)
        if expect_fail_open and count == 0:
            raise SystemExit(
                f"GATE FAILED at '{label}': {table} ({guc_label}): "
                f"expected fail-open (rows > 0), got 0 — COALESCE policy absent?"
            )
        if not expect_fail_open and count > 0:
            raise SystemExit(
                f"GATE FAILED at '{label}': {table} ({guc_label}): "
                f"expected fail-closed (0 rows), got {count} — NULLIF not applied?"
            )


def _check_phase(
    dsn: str,
    label: str,
    *,
    expect_fail_open: bool,
) -> None:
    """Assert fail-open (all rows visible without GUC) or fail-closed (no rows)."""
    print(f"\n=== {label} (expect {'FAIL-OPEN' if expect_fail_open else 'FAIL-CLOSED'}) ===")
    for table in _COALESCE_TABLES:
        _assert_single_table_phase(dsn, table, label, expect_fail_open=expect_fail_open)
        print(f"    {table}: OK")
    print(f"--- {label}: as expected")


def _check_invariants(dsn: str, label: str) -> None:
    """Assert that wrong-tenant GUC blocks and correct-tenant GUC allows.

    These invariants hold both before and after the migration because the
    COALESCE expression already isolates rows when a valid (wrong) UUID is
    provided — the fail-open only manifests when the GUC is absent or empty.
    """
    print(f"\n=== {label} — invariant check ===")

    for table in _COALESCE_TABLES:
        # Wrong tenant sees none of TENANT_A's rows:
        wrong_count = _count_rows_as_role(dsn, table, tenant_guc=TENANT_B)
        # Correct tenant sees exactly 1 row (we seeded one per tenant):
        right_count = _count_rows_as_role(dsn, table, tenant_guc=TENANT_A)

        if wrong_count != 1:
            raise SystemExit(
                f"INVARIANT FAILED at '{label}': {table}: wrong-tenant GUC "
                f"returned {wrong_count} rows, expected 1 (TENANT_B's own row)"
            )
        if right_count != 1:
            raise SystemExit(
                f"INVARIANT FAILED at '{label}': {table}: correct-tenant GUC "
                f"returned {right_count} rows, expected 1 (TENANT_A's row)"
            )
        print(f"    {table}: wrong-tenant={wrong_count} correct-tenant={right_count} OK")

    print(f"--- {label} invariants: PASSED")


def _check_precondition_abort(dsn: str) -> None:
    """Inject a mismatched row into analyses, prove upgrade aborts, then clean up."""
    print("\n=== precondition abort test ===")
    bad_id = "99999999-9999-9999-9999-000000000099"

    # Insert row whose tenant_id disagrees with the project's tenant_id.
    _exec_script(
        dsn,
        sql=(
            f"INSERT INTO analyses (id, project_id, tenant_id) VALUES "
            f"('{bad_id}'::uuid, '{PROJECT_A}'::uuid, '{TENANT_B}'::uuid)"
        ),
    )

    # Upgrade must abort with the precondition message.
    _exec_script_expect_error(
        dsn,
        emitted_sql("upgrade"),
        "P0-SEC-B PRECONDITION FAILED",
    )

    # Verify the COALESCE policies are still intact (upgrade rolled back).
    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pg_policies "
            "WHERE schemaname='public' AND tablename='project_states' "
            "AND policyname='project_states_select' "
            "AND qual LIKE '%COALESCE%'"
        )
        row = cur.fetchone()
        count = int(row[0]) if row else 0
    if count != 1:
        raise SystemExit(
            "GATE FAILED: precondition abort did not preserve COALESCE policy "
            f"(found {count} COALESCE policies on project_states after abort)"
        )

    # Remove the bad row so the real upgrade can proceed.
    _exec_script(dsn, sql=f"DELETE FROM analyses WHERE id = '{bad_id}'::uuid")
    print("--- precondition abort test: PASSED")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="do not drop the disposable DB")
    args = parser.parse_args()

    admin = _resolve_admin_dsn()
    target = admin.rsplit("/", 1)[0] + "/" + DB_NAME

    _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')
    _exec_script(admin, sql=f'CREATE DATABASE "{DB_NAME}"')

    try:
        # Load the COALESCE pre-state fixture.
        _exec_script(target, path=FIXTURE)

        # Step 1: confirm TRUE RED before migration.
        _check_phase(target, "pre-state", expect_fail_open=True)

        # Step 2: confirm invariants hold before migration.
        _check_invariants(target, "pre-state")

        # Step 3: prove precondition aborts on bad data.
        _check_precondition_abort(target)

        # Step 4: apply the migration.
        upgrade = emitted_sql("upgrade")
        _exec_script(target, sql=upgrade)

        # Step 5: confirm GREEN after migration.
        _check_phase(target, "after upgrade", expect_fail_open=False)

        # Step 6: confirm invariants hold after migration.
        _check_invariants(target, "after upgrade")

        # Step 7: downgrade and confirm RED returns.
        _exec_script(target, sql=emitted_sql("downgrade"))
        _check_phase(target, "after downgrade", expect_fail_open=True)

        # Step 8: re-apply and confirm GREEN (idempotent).
        _exec_script(target, sql=upgrade)
        _check_phase(target, "after re-apply", expect_fail_open=False)

    finally:
        if not args.keep:
            _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')

    print("\nP0-SEC-B GATE: PASSED (RED -> GREEN -> RED -> GREEN + invariants + precondition)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
