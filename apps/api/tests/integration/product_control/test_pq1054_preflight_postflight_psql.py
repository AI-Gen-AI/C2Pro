"""#1054: run the real operator preflight/postflight scripts through psql.

psql meta-commands (\\if, \\g, ON_ERROR_STOP) only exist in psql, so these
scripts run as a separate psql session against a fixture that is committed
and then dropped: the same production-shape fixture as the migration suite,
renamed to random identities. Covers:

(a) the pre-migration preflight runs without the anchor table;
(b) the postflight fails when the anchor table is missing;
(c) zero anchor rows fail;
(d) a wrong tenant or project fails;
(e) the valid anchor passes;
(f) no run prints the protected tenant id;
(g) a missing expected_tenant fails with a nonzero exit.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import UUID

import pytest

from tests.integration.product_control.test_pq1054_acceptance_tenant_binding_pg import (
    _DSN,
    PROJECT_Q,
    TENANT_A,
    TENANT_B,
    Fixture,
    _connect,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires PostgreSQL *_test DSN"),
]

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
PREFLIGHT = _SCRIPTS / "pq1054_acceptance_role_preflight.sql"
POSTFLIGHT = _SCRIPTS / "pq1054_acceptance_role_postflight.sql"
PSQL_ERROR_EXIT = 3  # psql exit status for a script error under ON_ERROR_STOP


def _psql(fx: Fixture, script: Path, expected_tenant: UUID | None) -> subprocess.CompletedProcess:
    psql = shutil.which("psql")
    assert psql, "psql is required to run the operator scripts"
    args = [psql, "-X", "-d", _DSN, "-f", "-"]
    if expected_tenant is not None:
        args[2:2] = ["-v", f"expected_tenant={expected_tenant}"]
    result = subprocess.run(
        args,
        input=fx.sql(script.read_text()),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # (f) No outcome may print the protected tenant ids.
    for tenant in (TENANT_A, TENANT_B):
        assert str(tenant) not in result.stdout + result.stderr
    return result


async def _with_committed_fixture(body, *, migrate: bool) -> None:
    conn = await _connect()
    fx = Fixture()
    try:
        async with conn.transaction():
            await fx.build(conn)
            if migrate:
                await fx.upgrade(conn)
        await body(conn, fx)
    finally:
        await conn.execute(f"DROP SCHEMA IF EXISTS {fx.schema}, {fx.anchor} CASCADE")
        for role in (fx.role, fx.app):
            await conn.execute(f"DROP OWNED BY {role}")
            await conn.execute(f"DROP ROLE {role}")
        await conn.close()


async def test_pre_migration_preflight_and_postflight_without_anchor_table() -> None:
    async def body(conn, fx: Fixture) -> None:
        # (a) The preflight is run before the migration: no anchor table yet.
        pre = _psql(fx, PREFLIGHT, None)
        assert pre.returncode == 0, pre.stderr
        assert "ERROR" not in pre.stderr
        # (b) The postflight never passes before the migration.
        post = _psql(fx, POSTFLIGHT, TENANT_A)
        assert post.returncode == PSQL_ERROR_EXIT
        assert "PQ1054_ANCHOR_TABLE_MISSING" in post.stderr
        assert "PASS" not in post.stdout + post.stderr

    await _with_committed_fixture(body, migrate=False)


async def test_postflight_fails_closed_unless_exactly_the_approved_binding() -> None:
    async def body(conn, fx: Fixture) -> None:
        def failed(expected: UUID | None, code: str) -> None:
            result = _psql(fx, POSTFLIGHT, expected)
            assert result.returncode == PSQL_ERROR_EXIT, result.stdout + result.stderr
            assert code in result.stderr
            assert "PASS" not in result.stdout + result.stderr

        # (g) No expected tenant: fails before reading anything.
        failed(None, "PQ1054_EXPECTED_TENANT_REQUIRED")
        # (c) Migrated, but the owner has not inserted the anchor.
        failed(TENANT_A, "PQ1054_ANCHOR_POSTFLIGHT_FAILED")

        await fx.bind(conn, TENANT_A)
        # (e) The valid anchor passes; the preflight still runs after migration.
        valid = _psql(fx, POSTFLIGHT, TENANT_A)
        assert valid.returncode == 0, valid.stderr
        assert "PQ1054_ANCHOR_POSTFLIGHT_PASS" in valid.stderr
        assert _psql(fx, PREFLIGHT, None).returncode == 0
        # (d) The operator expects another tenant than the one anchored.
        failed(TENANT_B, "PQ1054_ANCHOR_POSTFLIGHT_FAILED")

        anchor = f"{fx.anchor}.acceptance_tenant_binding"
        # (d) Anchored to a tenant that does not own the approved project.
        await conn.execute(f"UPDATE {anchor} SET tenant_id = $1", TENANT_B)
        failed(TENANT_B, "PQ1054_ANCHOR_POSTFLIGHT_FAILED")
        # (d) Another project: only reachable if the table's CHECK has drifted.
        await conn.execute(
            f"ALTER TABLE {anchor} DROP CONSTRAINT acceptance_tenant_binding_project_id_check"
        )
        await conn.execute(
            f"UPDATE {anchor} SET tenant_id = $1, project_id = $2", TENANT_A, PROJECT_Q
        )
        failed(TENANT_A, "PQ1054_ANCHOR_POSTFLIGHT_FAILED")

    await _with_committed_fixture(body, migrate=True)
