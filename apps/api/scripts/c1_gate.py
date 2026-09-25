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

Then, post-fix, proves every live write verb the migration grants -- not
merely row visibility:

    dlq_failed_tasks:       SELECT, INSERT, UPDATE
    wbs_nodes:              SELECT, INSERT, UPDATE, DELETE
    notification_configs:   SELECT, INSERT, UPDATE
    disclaimer_acceptances: SELECT, INSERT

For each write verb: correct tenant succeeds, wrong tenant cannot
affect/create the row, absent GUC fails closed, empty GUC fails closed. For
every table with UPDATE, additionally proves a row cannot have its own
tenant_id mutated to a different tenant while executing under its owning
tenant's context (RLS UPDATE policies apply their USING expression as the
WITH CHECK expression too when no WITH CHECK is given -- this proves that
holds here, rather than assuming it from documentation).

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
import uuid
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
TENANT_C = "cccccccc-0000-0000-0000-000000000003"
PROJECT_A = "cccccccc-cccc-cccc-cccc-00000000000a"
PROJECT_C = "cccccccc-cccc-cccc-cccc-00000000000c"

DLQ_ROW_A = "11111111-1111-1111-1111-000000000001"
WBS_ROW_A = "22222222-2222-2222-2222-000000000001"
NOTIF_ROW_A = "33333333-3333-3333-3333-000000000001"

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


def _exec_as_role(dsn: str, sql: str, *, tenant_guc: str | None) -> int:
    """Execute one write statement as the synthetic role; return rowcount."""
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, tenant_guc)
        try:
            cur.execute(sql)
            return cur.rowcount
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")


def _exec_as_role_expect_error(dsn: str, sql: str, *, tenant_guc: str | None) -> bool:
    """Execute a write statement expected to be rejected by RLS. Returns True if it raised."""
    with _connection(dsn) as conn, conn.cursor() as cur:
        _as_role(cur, tenant_guc)
        try:
            cur.execute(sql)
        except Exception:  # noqa: BLE001 - the exact rejection is what we're proving exists
            return True
        finally:
            cur.execute("RESET ROLE")
            cur.execute("RESET app.current_tenant")
        return False


def _admin_read(dsn: str, sql: str) -> tuple | None:
    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


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


def _check_insert_write_path(dsn: str, table: str, insert_sql: str) -> None:
    """Prove INSERT: wrong-tenant/absent/empty GUC rejected by WITH CHECK; correct tenant succeeds.

    ``insert_sql`` always creates a row whose tenant_id is TENANT_C (see
    fixture note: TENANT_C is never pre-seeded, so a successful insert can
    never collide with a unique constraint and be mistaken for an RLS
    rejection). Only the session GUC varies across attempts; a failed
    attempt never persists anything (autocommit, single-statement).
    """
    for guc_label, guc in (("wrong-tenant", TENANT_A), ("absent", None), ("empty", "")):
        if not _exec_as_role_expect_error(dsn, insert_sql, tenant_guc=guc):
            raise SystemExit(
                f"GATE FAILED: {table} INSERT under {guc_label} GUC should have been "
                f"rejected by WITH CHECK, but succeeded"
            )
    rowcount = _exec_as_role(dsn, insert_sql, tenant_guc=TENANT_C)
    if rowcount != 1:
        raise SystemExit(
            f"GATE FAILED: {table} INSERT under correct-tenant GUC affected "
            f"{rowcount} row(s), expected 1"
        )
    print("    INSERT: wrong-tenant/absent/empty GUC rejected, correct-tenant succeeds — OK")


def _check_update_write_path(
    dsn: str,
    table: str,
    row_id: str,
    owner_tenant: str,
    *,
    set_clause: str,
    verify_sql: str,
    expected_after: object,
) -> None:
    """Prove UPDATE: wrong-tenant/absent/empty GUC affect 0 rows; correct tenant applies and persists."""
    other_tenant = TENANT_B if owner_tenant == TENANT_A else TENANT_A
    update_sql = f"UPDATE {table} SET {set_clause} WHERE id = '{row_id}'::uuid"  # nosec B608

    for guc_label, guc in (("wrong-tenant", other_tenant), ("absent", None), ("empty", "")):
        rowcount = _exec_as_role(dsn, update_sql, tenant_guc=guc)
        if rowcount != 0:
            raise SystemExit(
                f"GATE FAILED: {table} UPDATE under {guc_label} GUC affected "
                f"{rowcount} row(s), expected 0"
            )

    rowcount = _exec_as_role(dsn, update_sql, tenant_guc=owner_tenant)
    if rowcount != 1:
        raise SystemExit(
            f"GATE FAILED: {table} UPDATE under correct-tenant GUC affected "
            f"{rowcount} row(s), expected 1"
        )

    row = _admin_read(dsn, verify_sql)
    actual = row[0] if row else None
    if actual != expected_after:
        raise SystemExit(
            f"GATE FAILED: {table} UPDATE under correct-tenant GUC did not persist "
            f"the new value (expected {expected_after!r}, found {actual!r})"
        )
    print(
        "    UPDATE: wrong-tenant/absent/empty GUC affect 0 rows, "
        "correct-tenant applies and persists — OK"
    )


def _check_tenant_id_mutation_rejected(dsn: str, table: str, row_id: str, owner_tenant: str) -> None:
    """A row cannot have its own tenant_id changed to another tenant under its own context."""
    other_tenant = TENANT_B if owner_tenant == TENANT_A else TENANT_A
    sql = f"UPDATE {table} SET tenant_id = '{other_tenant}'::uuid WHERE id = '{row_id}'::uuid"  # nosec B608

    raised = _exec_as_role_expect_error(dsn, sql, tenant_guc=owner_tenant)
    if not raised:
        raise SystemExit(
            f"GATE FAILED: {table} allowed UPDATE ... SET tenant_id = {other_tenant} on a "
            f"row owned by {owner_tenant} while executing under {owner_tenant}'s own context "
            f"— cross-tenant tenant_id mutation was NOT rejected"
        )

    row = _admin_read(dsn, f"SELECT tenant_id FROM {table} WHERE id = '{row_id}'::uuid")  # nosec B608
    actual = str(row[0]) if row else None
    if actual != owner_tenant:
        raise SystemExit(
            f"GATE FAILED: {table} row {row_id} tenant_id is {actual!r} after a rejected "
            f"mutation attempt, expected it unchanged at {owner_tenant!r}"
        )
    print(
        f"    UPDATE tenant_id mutation ({owner_tenant} -> {other_tenant}) "
        f"correctly rejected, row unchanged — OK"
    )


def _check_delete_write_path(dsn: str, table: str, row_id: str, owner_tenant: str) -> None:
    """Prove DELETE: wrong-tenant/absent/empty GUC affect 0 rows; correct tenant deletes."""
    other_tenant = TENANT_B if owner_tenant == TENANT_A else TENANT_A
    delete_sql = f"DELETE FROM {table} WHERE id = '{row_id}'::uuid"  # nosec B608

    for guc_label, guc in (("wrong-tenant", other_tenant), ("absent", None), ("empty", "")):
        rowcount = _exec_as_role(dsn, delete_sql, tenant_guc=guc)
        if rowcount != 0:
            raise SystemExit(
                f"GATE FAILED: {table} DELETE under {guc_label} GUC affected "
                f"{rowcount} row(s), expected 0"
            )

    rowcount = _exec_as_role(dsn, delete_sql, tenant_guc=owner_tenant)
    if rowcount != 1:
        raise SystemExit(
            f"GATE FAILED: {table} DELETE under correct-tenant GUC affected "
            f"{rowcount} row(s), expected 1"
        )
    print("    DELETE: wrong-tenant/absent/empty GUC affect 0 rows, correct-tenant deletes — OK")


def _check_all_write_paths(dsn: str) -> None:
    """Post-fix: prove every live write verb per table, matching MASTER's exact matrix.

    dlq_failed_tasks:       SELECT, INSERT, UPDATE
    wbs_nodes:              SELECT, INSERT, UPDATE, DELETE
    notification_configs:   SELECT, INSERT, UPDATE
    disclaimer_acceptances: SELECT, INSERT
    """
    print("\n=== post-fix write-path proofs (per live verb, not merely visibility) ===")

    # ── dlq_failed_tasks: INSERT, UPDATE (+ tenant_id mutation rejection) ────
    print("  dlq_failed_tasks:")
    new_id = str(uuid.uuid4())
    _check_insert_write_path(
        dsn,
        "dlq_failed_tasks",
        f"INSERT INTO dlq_failed_tasks (id, tenant_id, task_type, payload_json, error_message) "
        f"VALUES ('{new_id}'::uuid, '{TENANT_C}'::uuid, 'document_analysis', '{{}}'::jsonb, 'probe')",
    )
    _check_update_write_path(
        dsn,
        "dlq_failed_tasks",
        DLQ_ROW_A,
        TENANT_A,
        set_clause="status = 'retrying'",
        verify_sql=f"SELECT status FROM dlq_failed_tasks WHERE id = '{DLQ_ROW_A}'::uuid",  # nosec B608
        expected_after="retrying",
    )
    _check_tenant_id_mutation_rejected(dsn, "dlq_failed_tasks", DLQ_ROW_A, TENANT_A)

    # ── wbs_nodes: INSERT, UPDATE (+ tenant_id mutation rejection), DELETE ───
    print("  wbs_nodes:")
    new_id = str(uuid.uuid4())
    _check_insert_write_path(
        dsn,
        "wbs_nodes",
        f"INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt) "
        f"VALUES ('{new_id}'::uuid, '{PROJECT_C}'::uuid, '{TENANT_C}'::uuid, 'C.1', 'Root C', 1, 2)",
    )
    _check_update_write_path(
        dsn,
        "wbs_nodes",
        WBS_ROW_A,
        TENANT_A,
        set_clause="name = 'Root A renamed'",
        verify_sql=f"SELECT name FROM wbs_nodes WHERE id = '{WBS_ROW_A}'::uuid",  # nosec B608
        expected_after="Root A renamed",
    )
    _check_tenant_id_mutation_rejected(dsn, "wbs_nodes", WBS_ROW_A, TENANT_A)
    delete_id = str(uuid.uuid4())
    _exec_as_role(
        dsn,
        f"INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt) "
        f"VALUES ('{delete_id}'::uuid, '{PROJECT_A}'::uuid, '{TENANT_A}'::uuid, 'A.2', 'To delete', 3, 4)",
        tenant_guc=TENANT_A,
    )
    _check_delete_write_path(dsn, "wbs_nodes", delete_id, TENANT_A)

    # ── notification_configs: INSERT, UPDATE (+ tenant_id mutation rejection) ─
    print("  notification_configs:")
    new_id = str(uuid.uuid4())
    _check_insert_write_path(
        dsn,
        "notification_configs",
        f"INSERT INTO notification_configs (id, tenant_id) VALUES ('{new_id}'::uuid, '{TENANT_C}'::uuid)",
    )
    _check_update_write_path(
        dsn,
        "notification_configs",
        NOTIF_ROW_A,
        TENANT_A,
        set_clause="notification_channels = '[\"email\"]'::jsonb",
        verify_sql=(
            f"SELECT notification_channels FROM notification_configs "
            f"WHERE id = '{NOTIF_ROW_A}'::uuid"  # nosec B608
        ),
        expected_after=["email"],
    )
    _check_tenant_id_mutation_rejected(dsn, "notification_configs", NOTIF_ROW_A, TENANT_A)

    # ── disclaimer_acceptances: INSERT only (no UPDATE/DELETE live verb) ─────
    print("  disclaimer_acceptances:")
    new_id = str(uuid.uuid4())
    _check_insert_write_path(
        dsn,
        "disclaimer_acceptances",
        f"INSERT INTO disclaimer_acceptances (id, tenant_id, user_id, project_id, version) "
        f"VALUES ('{new_id}'::uuid, '{TENANT_C}'::uuid, "
        f"'dddddddd-dddd-dddd-dddd-000000000003'::uuid, 'proj-c', 'v1')",
    )

    print("--- all live write verbs proven per table ---")


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
        _check_all_write_paths(target)

        _exec_script(target, sql=emitted_sql("downgrade"))
        _check_deny_all(target, "after downgrade")

        _exec_script(target, sql=upgrade)
        _check_fail_closed_correct(target, "after re-apply")

    finally:
        if not args.keep:
            _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')

    print(
        "\nC1 GATE: PASSED (RED -> GREEN -> RED -> GREEN, incl. full per-verb "
        "write-path proofs and cross-tenant tenant_id mutation rejection)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
