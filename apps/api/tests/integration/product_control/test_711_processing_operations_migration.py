"""#711 processing-authority migration on a real PostgreSQL.

Proves the migration-owned security surface the ORM bootstrap cannot show:
the table is FORCE-RLS with fail-closed tenant policies (no tenant GUC sees
and writes nothing, one tenant never sees another's authority), constraints
reject invalid stage/phase/fence values, and downgrade/upgrade round-trips.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _head_revision,
    _recreate_scratch_database,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

BEFORE_711_FENCE = "20260927_0711"
_ROLE = "c2pro_711_rls_probe"


async def test_711_processing_operations_are_fail_closed_force_rls_and_round_trip() -> None:
    assert SCRATCH_DSN is not None
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", "head")
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == _head_revision()
            force = await conn.fetchrow(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'public.document_processing_operations'::regclass"
            )
            assert force["relrowsecurity"] and force["relforcerowsecurity"]
            policies = await conn.fetch(
                "SELECT cmd, coalesce(qual, with_check) AS predicate FROM pg_policies "
                "WHERE tablename = 'document_processing_operations' ORDER BY cmd"
            )
            assert sorted(p["cmd"] for p in policies) == ["DELETE", "INSERT", "SELECT", "UPDATE"]
            for policy in policies:
                assert "NULLIF" in policy["predicate"] and "COALESCE" not in policy["predicate"]

            # Probe as an ordinary (non-owner, non-BYPASSRLS) role.
            await conn.execute(f"DROP ROLE IF EXISTS {_ROLE}")
            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(
                f"GRANT SELECT, INSERT, UPDATE ON public.documents, "
                f"public.document_processing_operations TO {_ROLE}"
            )
            tenant_a, tenant_b = uuid4(), uuid4()
            document_id = uuid4()
            await conn.execute("SET session_replication_role = replica")  # seed FK parents only
            await conn.execute(
                "INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
                "upload_status) VALUES ($1, $2, $3, 'contract', 'c.pdf', 'uploaded')",
                document_id, tenant_a, uuid4(),
            )
            await conn.execute("SET session_replication_role = DEFAULT")

            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                # No tenant GUC: fail closed on write.
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute(
                            "INSERT INTO document_processing_operations "
                            "(document_id, tenant_id, stage, phase) "
                            "VALUES ($1, $2, 'INGESTION', 'PENDING')",
                            document_id, tenant_a,
                        )
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, true)", str(tenant_a)
                )
                await conn.execute(
                    "INSERT INTO document_processing_operations "
                    "(document_id, tenant_id, stage, phase) VALUES ($1, $2, 'INGESTION', 'PENDING')",
                    document_id, tenant_a,
                )
                assert await conn.fetchval("SELECT count(*) FROM document_processing_operations") == 1
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, true)", str(tenant_b)
                )
                assert await conn.fetchval("SELECT count(*) FROM document_processing_operations") == 0
                await conn.execute("SELECT set_config('app.current_tenant', '', true)")
                assert await conn.fetchval("SELECT count(*) FROM document_processing_operations") == 0

            for bad in (
                "UPDATE document_processing_operations SET stage = 'BOGUS'",
                "UPDATE document_processing_operations SET phase = 'BOGUS'",
                "UPDATE document_processing_operations SET fencing_token = -1",
            ):
                with pytest.raises(asyncpg.CheckViolationError):
                    await conn.execute(bad)
            await conn.execute(f"REVOKE ALL ON public.documents, public.document_processing_operations FROM {_ROLE}")
            await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}")
            await conn.execute(f"DROP ROLE {_ROLE}")
        finally:
            await conn.close()

        _alembic("downgrade", BEFORE_711_FENCE)
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            assert await conn.fetchval(
                "SELECT to_regclass('public.document_processing_operations')"
            ) is None
        finally:
            await conn.close()
        _alembic("upgrade", "head")
    finally:
        await _drop_scratch_database()
