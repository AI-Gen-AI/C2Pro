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
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    REPO_ROOT
    / "apps/api/alembic/versions/20260902_0001_p0_sec_a_data_api_containment.py"
)
FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_a_prestate.sql"
LINT = REPO_ROOT / "apps/api/scripts/supabase_security_lint.py"
DB_NAME = "p0_sec_a_gate"


def psql(dsn: str, *args: str, sql: str | None = None, path: Path | None = None) -> None:
    cmd = ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-q", *args]
    if sql:
        cmd += ["-c", sql]
    if path:
        cmd += ["-f", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"psql failed:\n{result.stderr}")


def emitted_sql(direction: str) -> str:
    collected: list[str] = []
    stub = types.ModuleType("alembic")
    stub.op = types.SimpleNamespace(execute=lambda s: collected.append(str(s)))
    sys.modules["alembic"] = stub
    spec = importlib.util.spec_from_file_location("p0_sec_a_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    getattr(module, direction)()
    del sys.modules["alembic"]
    return "\n".join(s.strip().rstrip(";") + ";" for s in collected)


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
    args = parser.parse_args()
    if not args.admin_dsn:
        print("pass --admin-dsn or set ADMIN_DSN", file=sys.stderr)
        return 2

    admin = args.admin_dsn.replace("postgresql+asyncpg://", "postgresql://")
    target = admin.rsplit("/", 1)[0] + "/" + DB_NAME

    psql(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')
    psql(admin, sql=f'CREATE DATABASE "{DB_NAME}"')
    try:
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
            psql(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')

    print("\nP0-SEC-A GATE: PASSED (RED -> GREEN -> RED -> GREEN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
