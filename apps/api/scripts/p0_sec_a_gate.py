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
    python apps/api/scripts/p0_sec_a_gate.py --admin-dsn postgresql://postgres@localhost:5432/postgres
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p0_sec_a_common import REPO_ROOT, emitted_sql  # noqa: E402

FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_a_prestate.sql"
LINT = REPO_ROOT / "apps/api/scripts/supabase_security_lint.py"
DB_NAME = "p0_sec_a_gate"


def psql(dsn: str, *args: str, sql: str | None = None, path: Path | None = None) -> None:
    cmd = ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-q", *args]
    if sql:
        cmd += ["-c", sql]
    if path:
        cmd += ["-f", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        raise SystemExit(f"psql failed:\n{result.stderr}")


def role_exists(dsn: str, role: str) -> bool:
    """Check for a role without interpolating it into SQL."""
    result = subprocess.run(  # noqa: S603
        ["psql", dsn, "-tA", "-v", "role_name", "-c",
         "SELECT 1 FROM pg_roles WHERE rolname = current_setting('p0sec.role')"],
        capture_output=True, text=True,
        env={**os.environ, "PGOPTIONS": f"-c p0sec.role={role}"},
    )
    return bool(result.stdout.strip())


def lint_passes(dsn: str) -> bool:
    result = subprocess.run(
        [sys.executable, str(LINT), "--dsn", dsn], capture_output=True, text=True
    )
    print(result.stdout.strip()[-2000:])
    return result.returncode == 0


def phase(label: str, dsn: str, expect_pass: bool) -> None:
    print(f"\n=== {label} (expect lint {'PASS' if expect_pass else 'FAIL'}) ===")
    ok = lint_passes(dsn)
    if ok != expect_pass:
        raise SystemExit(
            f"GATE FAILED at '{label}': lint {'passed' if ok else 'failed'}, "
            f"expected {'pass' if expect_pass else 'fail'}"
        )
    print(f"--- {label}: as expected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-dsn", default=os.environ.get("ADMIN_DSN"))
    parser.add_argument("--keep", action="store_true", help="do not drop the disposable DB")
    parser.add_argument(
        "--mode",
        choices=["full", "bare"],
        default="full",
        help="full: Supabase-shaped pre-state cycle. bare: plain PostgreSQL with no "
        "anon/authenticated roles, proving the migration is portable.",
    )
    args = parser.parse_args()
    if not args.admin_dsn:
        print("pass --admin-dsn or set ADMIN_DSN", file=sys.stderr)
        return 2

    admin = args.admin_dsn.replace("postgresql+asyncpg://", "postgresql://")

    db_name = DB_NAME if args.mode == "full" else DB_NAME + "_bare"
    target = admin.rsplit("/", 1)[0] + "/" + db_name

    psql(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')
    psql(admin, sql=f'CREATE DATABASE "{db_name}"')
    try:
        if args.mode == "bare":
            # Reproduces CI and local development: a plain PostgreSQL instance
            # where the Supabase platform roles simply do not exist. Naming them
            # literally aborted the entire migration chain with
            # `role "anon" does not exist`, which took every DB-backed lane down.
            for role in ("anon", "authenticated"):
                if role_exists(target, role):
                    raise SystemExit(
                        f"bare mode needs a cluster without the '{role}' role; "
                        f"this cluster has it. Run bare mode on a clean cluster."
                    )
            psql(target, sql="CREATE TABLE public.bare_probe (id int); "
                             "CREATE SEQUENCE public.bare_probe_seq")
            print("\n=== bare PostgreSQL: upgrade must apply cleanly ===")
            psql(target, sql=emitted_sql("upgrade"))
            print("--- bare upgrade: OK")
            print("=== bare PostgreSQL: downgrade must apply cleanly ===")
            psql(target, sql=emitted_sql("downgrade"))
            print("--- bare downgrade: OK")
            print("=== bare PostgreSQL: re-apply must apply cleanly ===")
            psql(target, sql=emitted_sql("upgrade"))
            print("--- bare re-apply: OK")
            print("\nP0-SEC-A GATE (bare): PASSED (portable on plain PostgreSQL)")
            return 0

        psql(target, path=FIXTURE)
        phase("pre-state", target, expect_pass=False)

        upgrade = emitted_sql("upgrade")
        psql(target, sql=upgrade)
        phase("after upgrade", target, expect_pass=True)

        psql(target, sql=emitted_sql("downgrade"))
        phase("after downgrade", target, expect_pass=False)

        psql(target, sql=upgrade)
        phase("after re-apply", target, expect_pass=True)
    finally:
        if not args.keep:
            psql(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')

    print("\nP0-SEC-A GATE: PASSED (RED -> GREEN -> RED -> GREEN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
