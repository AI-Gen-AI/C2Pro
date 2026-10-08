"""PQ-HITL-04B acceptance: actual tenant RLS and ledger CAS on scratch PostgreSQL.

Runs ONLY when C2PRO_MIGRATION_SCRATCH_DSN points to an ephemeral *_test DB.
Synthetic audit rows are fixture-seeded as the DB owner with triggers disabled
because this test isolates RLS/unique-index behavior, NOT candidate-commit
acceptance. It never accesses or changes a production review or artifact.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _recreate_scratch_database,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires disposable *_test scratch database"),
]

_ROLE = "c2pro_hitl_finding_rls_probe"

_SEED = """
INSERT INTO public.hitl_finding_decisions (
    event_id, tenant_id, project_id, review_row_id, document_id,
    document_revision_id, artifact_id, artifact_version, artifact_hash,
    generation, fencing_token, thread_id, checkpoint_id,
    finding_id, source_item_id, source_ordinal, finding_kind,
    action, reviewer_id, created_by,
    expected_ledger_revision, ledger_revision, idempotency_key, evidence_refs
) VALUES (
    gen_random_uuid(), $1::uuid, gen_random_uuid(), $2::uuid, gen_random_uuid(),
    gen_random_uuid(), gen_random_uuid(), 1, repeat('a', 64),
    3, 10, 'synthetic-checkpoint-thread', 'checkpoint-only',
    repeat('b', 64), 'risk-sha256:' || repeat('c', 64), 0, 'RISK',
    'CONFIRMED', 'synthetic-human', 'synthetic-human',
    $4::bigint, $5::bigint, $3::varchar, '[]'::jsonb
) RETURNING event_id
"""


async def _seed(conn, tenant: UUID, row_id: UUID, key: str,
                expected: int = 0, version: int = 1) -> UUID:
    return await conn.fetchval(_SEED, tenant, row_id, key, expected, version)


async def test_finding_ledger_forced_rls_tenant_partition_unique_cas_and_audit_retention() -> None:
    await _recreate_scratch_database()
    role_created = False
    try:
        _alembic("upgrade", "20261008_0001")
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            tenant_a, tenant_b, row_a, row_b = uuid4(), uuid4(), uuid4(), uuid4()
            await conn.execute("SET session_replication_role = replica")
            try:
                event_a = await _seed(conn, tenant_a, row_a, "a-request-000001")
                event_b = await _seed(conn, tenant_b, row_b, "b-request-000001")
                # Constraints remain active even when fixture triggers are disabled:
                # a replay key cannot name two different events in one review row.
                with pytest.raises(asyncpg.UniqueViolationError):
                    await _seed(conn, tenant_a, row_a, "a-request-000001")
                with pytest.raises(asyncpg.CheckViolationError):
                    await _seed(conn, tenant_a, uuid4(), "a-cas-invalid01",
                                expected=0, version=3)
            finally:
                await conn.execute("SET session_replication_role = origin")

            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            role_created = True
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.hitl_finding_decisions TO {_ROLE}"
            )
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, true)",
                    str(tenant_a),
                )
                rows = await conn.fetch(
                    "SELECT event_id FROM public.hitl_finding_decisions ORDER BY event_id"
                )
                assert [r["event_id"] for r in rows] == [event_a]
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.hitl_finding_decisions WHERE event_id = $1",
                    event_b,
                ) == 0
                # No UPDATE/DELETE policy exists: an authenticated tenant can't
                # rewrite/delete its own immutable historical decision.
                assert await conn.execute(
                    "DELETE FROM public.hitl_finding_decisions WHERE event_id = $1",
                    event_a,
                ) == "DELETE 0"
                assert await conn.execute(
                    "UPDATE public.hitl_finding_decisions SET reason = 'tampered' "
                    "WHERE event_id = $1", event_a
                ) == "UPDATE 0"
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                await conn.execute("SELECT set_config('app.current_tenant', '', true)")
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.hitl_finding_decisions"
                ) == 0
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, true)",
                    str(tenant_b),
                )
                rows = await conn.fetch("SELECT event_id FROM public.hitl_finding_decisions")
                assert [r["event_id"] for r in rows] == [event_b]
            assert await conn.fetchval(
                "SELECT count(*) FROM public.hitl_finding_decisions"
            ) == 2
            # A populated append-only ledger cannot be downgraded to erase audit.
            with pytest.raises(AssertionError, match="cannot downgrade populated"):
                _alembic("downgrade", "20261007_0003")
            assert await conn.fetchval(
                "SELECT version_num FROM alembic_version"
            ) == "20261008_0001"
        finally:
            if role_created:
                await conn.execute(
                    f"REVOKE ALL ON public.hitl_finding_decisions FROM {_ROLE}"
                )
                await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}")
                await conn.execute(f"DROP ROLE {_ROLE}")
            await conn.close()
    finally:
        await _drop_scratch_database()
