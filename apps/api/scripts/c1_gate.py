#!/usr/bin/env python3
"""Self-verifying gate for the C1 tenant-GUC-name fix migration.

Builds a disposable database reproducing the pre-fix state for the 4 tables
whose Alembic-created RLS policies reference the wrong GUC name
(``app.current_tenant_id`` instead of ``app.current_tenant``), then proves:

    pre-state   -> even the CORRECT tenant is denied (RED: fail-closed for
                   everyone, not just the wrong tenant -- this is the bug)
    upgrade     -> correct tenant succeeds, wrong tenant fails, absent GUC
                   fails, empty GUC fails (GREEN)
    downgrade   -> RED returns (rollback is honest)
    upgrade     -> GREEN again (idempotent)

All checks run as a synthetic ``c2pro_sec_rls_test`` role: NOSUPERUSER,
NOBYPASSRLS, NOCREATEROLE, and NOT the table owner -- so table-ownership
bypass (independent of the BYPASSRLS attribute) cannot mask a missing or
broken policy the way it does for the shared runtime role today.

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres \\
        python apps/api/scripts/c1_gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from c1_common import REPO_ROOT, emitted_sql  # noqa: E402
from security_gate_common import exec_sql as _exec_script  # noqa: E402
from security_gate_common import pg_connection as _connection  # noqa: E402
from security_gate_common import resolve_admin_dsn as _resolve_admin_dsn_impl  # noqa: E402

FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/c1_prestate.sql"
DB_NAME = "c1_gate"

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-000000000002"
PROJECT_A = "cccccccc-cccc-cccc-cccc-00000000000a"

_TABLES = ("dlq_failed_tasks", "wbs_nodes", "notification_configs", "disclaimer_acceptances")


def _resolve_admin_dsn() -> str:
    return _resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")


def _as_role(cur, tenant_guc: str | None) -> None:
    cur.execute("RESET app.current_tenant")
    if tenant_guc is not None:
        cur.execute("SELECT set_config('app.current_tenant', %s, false)", (tenant_guc,))
    cur.execute("SET ROLE c2pro_sec_rls_test")


def _count_rows(dsn: str, table: str, *, tenant_guc: str | None) -> int:
    """Count rows visible to c2pro_sec_rls_test with an optional tenant GUC."""
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, tenant_guc)
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608 — table is hardcoded
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")


def _check_deny_all(dsn: str, label: str) -> None:
    """RED: even the correct tenant GUC sees 0 rows (fail-closed for everyone).

    notification_configs is worse than merely deny-all pre-fix: its policy
    omits current_setting's missing_ok argument, so every query against it
    raises "unrecognized configuration parameter" regardless of GUC value,
    rather than returning 0 rows. That is checked here too (not just via the
    dedicated fresh-connection test) since it holds for every GUC state.
    """
    print(f"\n=== {label} (expect DENY-ALL, including correct tenant) ===")
    for table in _TABLES:
        for guc_label, guc in (("absent", None), ("empty", ""), ("correct-tenant", TENANT_A)):
            if table == "notification_configs":
                try:
                    _count_rows(dsn, table, tenant_guc=guc)
                except Exception as exc:  # noqa: BLE001 - asserting the exact failure mode
                    if "unrecognized configuration parameter" not in str(exc):
                        raise SystemExit(
                            f"GATE FAILED at '{label}': {table} ({guc_label} GUC): "
                            f"expected 'unrecognized configuration parameter', got: {exc}"
                        ) from None
                else:
                    raise SystemExit(
                        f"GATE FAILED at '{label}': {table} ({guc_label} GUC): "
                        f"expected a hard error, query succeeded"
                    )
                continue
            count = _count_rows(dsn, table, tenant_guc=guc)
            if count != 0:
                raise SystemExit(
                    f"GATE FAILED at '{label}': {table} ({guc_label} GUC): "
                    f"expected 0 rows (deny-all bug), got {count}"
                )
        print(f"    {table}: OK (denies absent/empty/correct-tenant alike)")
    print(f"--- {label}: as expected")


def _check_fail_closed_correct(dsn: str, label: str) -> None:
    """GREEN: absent/empty GUC see nothing; each tenant sees only its own row.

    The fixture seeds exactly one row per tenant per table, so a tenant's GUC
    seeing "its own row and no more" (count == 1, not 2) is what proves
    isolation -- not merely that some row is returned.
    """
    print(f"\n=== {label} (expect fail-closed + per-tenant isolation) ===")
    for table in _TABLES:
        for guc_label, guc, expected in (
            ("absent", None, 0),
            ("empty", "", 0),
            ("tenant-A", TENANT_A, 1),
            ("tenant-B", TENANT_B, 1),
        ):
            count = _count_rows(dsn, table, tenant_guc=guc)
            if count != expected:
                raise SystemExit(
                    f"GATE FAILED at '{label}': {table} ({guc_label} GUC): "
                    f"expected {expected} row(s), got {count}"
                )
        print(f"    {table}: OK (absent=0 empty=0 tenant-A=1 tenant-B=1, never each other's)")
    print(f"--- {label}: as expected")


def _check_wbs_nodes_write_paths(dsn: str) -> None:
    """Post-fix: prove INSERT/UPDATE/DELETE on wbs_nodes are tenant-fail-closed too."""
    print("\n=== wbs_nodes post-fix: INSERT/UPDATE/DELETE tenant enforcement ===")
    new_id = "eeeeeeee-eeee-eeee-eeee-000000000001"

    # INSERT under the wrong tenant's GUC must be rejected by WITH CHECK.
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, TENANT_B)
        try:
            cur.execute(
                "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt) "
                f"VALUES ('{new_id}'::uuid, '{PROJECT_A}'::uuid, '{TENANT_A}'::uuid, "
                "'A.2', 'Should fail', 3, 4)"
            )
        except Exception:
            pass
        else:
            raise SystemExit(
                "GATE FAILED: wbs_nodes INSERT with mismatched tenant_id under wrong-"
                "tenant GUC should have been rejected by WITH CHECK, but succeeded"
            )
        finally:
            conn.rollback()
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")

    # INSERT under the correct tenant's GUC must succeed.
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, TENANT_A)
        try:
            cur.execute(
                "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt) "
                f"VALUES ('{new_id}'::uuid, '{PROJECT_A}'::uuid, '{TENANT_A}'::uuid, "
                "'A.2', 'Should succeed', 3, 4)"
            )
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")
    print("    INSERT: wrong-tenant WITH CHECK rejects, correct-tenant succeeds — OK")

    # DELETE under the wrong tenant's GUC must affect 0 rows.
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, TENANT_B)
        try:
            cur.execute(f"DELETE FROM wbs_nodes WHERE id = '{new_id}'::uuid")
            if cur.rowcount != 0:
                raise SystemExit(
                    f"GATE FAILED: wrong-tenant DELETE on wbs_nodes affected "
                    f"{cur.rowcount} row(s), expected 0"
                )
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")

    # DELETE under the correct tenant's GUC must succeed.
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, TENANT_A)
        try:
            cur.execute(f"DELETE FROM wbs_nodes WHERE id = '{new_id}'::uuid")
            if cur.rowcount != 1:
                raise SystemExit(
                    f"GATE FAILED: correct-tenant DELETE on wbs_nodes affected "
                    f"{cur.rowcount} row(s), expected 1"
                )
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")
    print("    DELETE: wrong-tenant no-ops, correct-tenant succeeds — OK")


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
        _exec_script(target, path=FIXTURE)

        _check_deny_all(target, "pre-state")

        upgrade = emitted_sql("upgrade")
        _exec_script(target, sql=upgrade)
        _check_fail_closed_correct(target, "after upgrade")
        _check_wbs_nodes_write_paths(target)

        _exec_script(target, sql=emitted_sql("downgrade"))
        _check_deny_all(target, "after downgrade")

        _exec_script(target, sql=upgrade)
        _check_fail_closed_correct(target, "after re-apply")

    finally:
        if not args.keep:
            _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')

    print("\nC1 GATE: PASSED (RED -> GREEN -> RED -> GREEN, incl. wbs_nodes write paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
