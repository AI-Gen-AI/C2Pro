"""Adversarial PostgreSQL check of #966's downgrade audit-retention guard.

This test runs ONLY against the dedicated migrated *_test PostgreSQL database
used by CI. It creates a disposable separate table/role inside a transaction,
executes the exact Alembic downgrade DO guard with that table substituted,
and rolls back everything. It NEVER downgrades or deletes the real ledger.
"""

from __future__ import annotations

import os
from importlib import util
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

import pytest

asyncpg = pytest.importorskip("asyncpg")

_DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires migrated PostgreSQL *_test DSN"),
]


def _downgrade_guard() -> str:
    """Read the guard FROM THE ACTUAL migration, not a reimplementation."""
    migration = (
        Path(__file__).resolve().parents[3]
        / "alembic/versions/20261008_0001_hitl_finding_decisions.py"
    )
    spec = util.spec_from_file_location("hitl_downgrade_rls_guard_test", migration)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    guard = module.DOWNGRADE_STATEMENTS[0]
    assert "set_config('row_security', 'off', true)" in guard
    assert "SELECT 1 FROM public.hitl_finding_decisions LIMIT 1" in guard
    return guard


async def test_downgrade_guard_cannot_miss_other_tenant_audit_rows() -> None:
    """Test missing tenant, wrong tenant, matching tenant, and empty ledger.

    FORCE RLS + row_security=off must raise when policies would hide rows;
    an owning role without BYPASSRLS must NOT turn hidden audit data into
    apparent emptiness. Matching-tenant rows must raise restrict_violation.
    """
    assert _DSN is not None
    assert urlparse(_DSN).path.rsplit("/", 1)[-1].endswith("_test")

    suffix = uuid4().hex[:12]
    role = f"hitl_dg_owner_{suffix}"
    table = f"hitl_dg_probe_{suffix}"
    name = f"public.{table}"
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    guard = _downgrade_guard().replace(
        "public.hitl_finding_decisions", name
    )

    conn = await asyncpg.connect(_DSN)
    try:
        # Every object and grant is undone with the outer transaction.
        async with conn.transaction():
            await conn.execute(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"CREATE TABLE {name} (tenant_id uuid NOT NULL)")
            await conn.execute(f"ALTER TABLE {name} OWNER TO {role}")
            await conn.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
            await conn.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
            await conn.execute(
                f"CREATE POLICY probe_select ON {name} FOR SELECT USING "
                "(tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)"
            )
            # Fixture insert by postgres, before lowering privileges.
            await conn.execute(
                f"INSERT INTO {name} (tenant_id) VALUES ($1::uuid)",
                tenant_b,
            )
            await conn.execute(f"SET LOCAL ROLE {role}")

            for tenant_setting in ("", tenant_a):
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, true)",
                    tenant_setting,
                )
                with pytest.raises(asyncpg.PostgresError) as exc:
                    async with conn.transaction():
                        await conn.execute(guard)
                assert exc.value.sqlstate == "42501"
                assert "row-level security" in str(exc.value).lower()

            # Even when the current tenant can see the entry, the guard
            # must reject the downgrade because immutable history exists.
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, true)", tenant_b
            )
            with pytest.raises(asyncpg.PostgresError) as exc:
                async with conn.transaction():
                    await conn.execute(guard)
            assert exc.value.sqlstate == "23001"
            assert "cannot downgrade populated" in str(exc.value)

            # Even an empty ledger is allowed to fail CLOSED for an
            # RLS-bound owner: PostgreSQL checks policy applicability,
            # not the count of rows. Only privileged maintenance can
            # intentionally pass the empty-table guard.
            await conn.execute("RESET ROLE")
            await conn.execute(f"DELETE FROM {name}")
            await conn.execute(f"SET LOCAL ROLE {role}")
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, true)", tenant_a
            )
            with pytest.raises(asyncpg.PostgresError) as exc:
                async with conn.transaction():
                    await conn.execute(guard)
            assert exc.value.sqlstate == "42501"

            await conn.execute("RESET ROLE")
            await conn.execute(guard)
    finally:
        await conn.close()
