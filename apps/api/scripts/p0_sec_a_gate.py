#!/usr/bin/env python3
"""Self-verifying gate for the P0-SEC-A containment migration.

Builds a disposable database that reproduces the production pre-state, then
proves the full cycle:

    pre-state        -> lint MUST FAIL   (the exposure is real / test is RED-first)
    upgrade          -> lint MUST PASS   (containment works)
    downgrade        -> lint MUST FAIL   (rollback is honest about what it restores)
    upgrade (again)  -> lint MUST PASS   (idempotent)

A gate that only checks the post-migration state cannot tell a real fix from a
test that never had teeth, so each RED phase is asserted explicitly.

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres \\
        python apps/api/scripts/p0_sec_a_gate.py
DSN is read exclusively from the P0_SEC_ADMIN_DSN environment variable and must
resolve to a loopback host (localhost / 127.0.0.1 / ::1). Remote or cloud hosts
are rejected at startup to prevent accidental use against production databases.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import supabase_security_lint as _lint  # noqa: E402
from p0_sec_a_common import REPO_ROOT, emitted_sql  # noqa: E402
from security_gate_common import exec_sql as _pg_exec  # noqa: E402
from security_gate_common import resolve_admin_dsn as _resolve_admin_dsn_impl  # noqa: E402

FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_a_prestate.sql"
DB_NAME = "p0_sec_a_gate"


def _resolve_admin_dsn() -> str:
    return _resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")


def _role_exists(dsn: str, role: str) -> bool:
    """Check whether a PostgreSQL role exists using a parameterized query."""
    try:
        import psycopg
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            return cur.fetchone() is not None
    except ImportError:
        import psycopg2
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                return cur.fetchone() is not None
        finally:
            conn.close()


def _lint_passes(dsn: str) -> bool:
    """Invoke the P0-SEC-A-scoped lint check and return whether it passed.

    Scope is restricted to "p0_sec_a" so that P0-SEC-B blockers legitimately
    present in the P0-SEC-A historical fixture (COALESCE fail-open policies that
    P0-SEC-A intentionally does not touch) do not cause false failures here.
    The global linter (scope=None) and the P0-SEC-B gate remain responsible for
    those findings.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _lint.run(dsn, scope="p0_sec_a")
    output = buf.getvalue()
    print(output.strip()[-2000:])
    return rc == 0


def phase(label: str, dsn: str, expect_pass: bool) -> None:
    print(f"\n=== {label} (expect lint {'PASS' if expect_pass else 'FAIL'}) ===")
    ok = _lint_passes(dsn)
    if ok != expect_pass:
        raise SystemExit(
            f"GATE FAILED at '{label}': lint {'passed' if ok else 'failed'}, "
            f"expected {'pass' if expect_pass else 'fail'}"
        )
    print(f"--- {label}: as expected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="do not drop the disposable DB")
    parser.add_argument(
        "--mode",
        choices=["full", "bare"],
        default="full",
        help="full: Supabase-shaped pre-state cycle. bare: plain PostgreSQL with no "
        "anon/authenticated roles, proving the migration is portable.",
    )
    args = parser.parse_args()

    admin = _resolve_admin_dsn()  # exits if DSN missing or non-loopback

    db_name = DB_NAME if args.mode == "full" else DB_NAME + "_bare"
    target = admin.rsplit("/", 1)[0] + "/" + db_name

    _pg_exec(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')
    _pg_exec(admin, sql=f'CREATE DATABASE "{db_name}"')
    try:
        if args.mode == "bare":
            # Reproduces CI and local development: a plain PostgreSQL instance
            # where the Supabase platform roles simply do not exist. Naming them
            # literally aborted the entire migration chain with
            # `role "anon" does not exist`, which took every DB-backed lane down.
            for role in ("anon", "authenticated"):
                if _role_exists(target, role):
                    raise SystemExit(
                        f"bare mode needs a cluster without the '{role}' role; "
                        f"this cluster has it. Run bare mode on a clean cluster."
                    )
            _pg_exec(target, sql="CREATE TABLE public.bare_probe (id int)")
            _pg_exec(target, sql="CREATE SEQUENCE public.bare_probe_seq")
            print("\n=== bare PostgreSQL: upgrade must apply cleanly ===")
            _pg_exec(target, sql=emitted_sql("upgrade"))
            print("--- bare upgrade: OK")
            print("=== bare PostgreSQL: downgrade must apply cleanly ===")
            _pg_exec(target, sql=emitted_sql("downgrade"))
            print("--- bare downgrade: OK")
            print("=== bare PostgreSQL: re-apply must apply cleanly ===")
            _pg_exec(target, sql=emitted_sql("upgrade"))
            print("--- bare re-apply: OK")
            print("\nP0-SEC-A GATE (bare): PASSED (portable on plain PostgreSQL)")
            return 0

        _pg_exec(target, path=FIXTURE)
        phase("pre-state", target, expect_pass=False)

        upgrade = emitted_sql("upgrade")
        _pg_exec(target, sql=upgrade)
        phase("after upgrade", target, expect_pass=True)

        _pg_exec(target, sql=emitted_sql("downgrade"))
        phase("after downgrade", target, expect_pass=False)

        _pg_exec(target, sql=upgrade)
        phase("after re-apply", target, expect_pass=True)
    finally:
        if not args.keep:
            _pg_exec(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')

    print("\nP0-SEC-A GATE: PASSED (RED -> GREEN -> RED -> GREEN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
