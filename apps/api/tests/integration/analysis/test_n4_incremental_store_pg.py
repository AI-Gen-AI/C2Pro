"""V4 WBS 2.2/2.5/2.6: real PostgreSQL scratch-only budget/ledger checks.

Requires C2PRO_N4_SCRATCH_DSN ending in *_test, upgraded with Alembic.
Never creates, modifies or drops a production DB, and never calls providers.
"""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlparse
from uuid import UUID, uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.analysis.adapters.persistence.n4_incremental_store import (
    N4BudgetError,
    N4BudgetExceeded,
    N4LedgerError,
    account_call,
    commit_window,
    create_run,
    progress,
    reserve_call,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.processing_authority import (
    ProcessingAuthority,
    ProcessingAuthorityLost,
    ProcessingStage,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
if _DSN:
    assert urlparse(_DSN).path.rstrip("/").endswith("_test"), "scratch DB must end with _test"

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires disposable upgraded *_test PostgreSQL"),
]


def _new_authority(tenant: UUID, document: UUID, revision: UUID) -> ProcessingAuthority:
    return ProcessingAuthority(
        tenant_id=tenant, document_id=document, revision_id=revision,
        generation=1, stage=ProcessingStage.ANALYSIS, attempt_id=uuid4(),
        owner_token=uuid4(), fencing_token=1,
    )


async def _seed_identity(
    conn, *, authority: ProcessingAuthority, project: UUID,
    create_tenant: bool = True,
) -> None:
    t = authority.tenant_id
    doc = authority.document_id
    rev = authority.revision_id
    # Existing document-work-index trigger requires a tenant context even
    # during synthetic fixture construction. This connection is scratch-only.
    await conn.execute(
        "SELECT set_config('app.current_tenant', $1, false)", str(t)
    )
    if create_tenant:
        await conn.execute("""
            INSERT INTO public.tenants (id, name, slug, subscription_plan)
            VALUES ($1, 'N4 scratch tenant', $2, 'free')
        """, t, f"n4-test-{t.hex}")
    await conn.execute("""
        INSERT INTO public.projects
          (id, tenant_id, name, project_type, status)
        VALUES ($1, $2, 'N4 scratch test', 'construction', 'active')
    """, project, t)
    await conn.execute("""
        INSERT INTO public.documents
          (id, project_id, tenant_id, filename, document_type)
        VALUES ($1, $2, $3, 'scratch-contract.pdf', 'contract')
    """, doc, project, t)
    await conn.execute("""
        INSERT INTO public.document_revisions
          (revision_id, document_id, project_id, tenant_id, rev_no,
           blob_hash, blob_key, valid_from)
        VALUES ($1, $2, $3, $4, 1, $5, 'scratch/source', clock_timestamp())
    """, rev, doc, project, t, "a" * 64)
    await conn.execute("""
        INSERT INTO public.document_processing_operations
          (document_id, tenant_id, revision_id, generation, stage, phase,
           attempt_id, owner_token, fencing_token, lease_expires_at)
        VALUES ($1, $2, $3, 1, 'ANALYSIS', 'RUNNING',
                $4, $5, 1, clock_timestamp() + interval '1 hour')
    """, doc, t, rev, authority.attempt_id, authority.owner_token)


async def _seed_caps(conn, tenant, project, document, amount):
    for kind, scope_id in [
        ("TENANT", tenant), ("PROJECT", project), ("DOCUMENT", document)
    ]:
        await conn.execute("""
            INSERT INTO public.n4_budget_buckets
              (tenant_id, scope_kind, scope_id, period_key, cap_usd)
            VALUES ($1, $2, $3, '2026-11', $4)
        """, tenant, kind, scope_id, Decimal(amount))


async def test_real_postgres_n4_idempotency_budget_resume_fencing_and_rls():
    dsn = _DSN
    async_dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    a = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    source = "The Contractor shall comply with clause 9.6. " * 35
    windows = plan_n4_source_windows(
        source, revision_id=str(a.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    assert len(windows) > 1
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=a, project=project)
        await _seed_caps(conn, a.tenant_id, project, a.document_id, "1.000000")
    finally:
        await conn.close()

    engine = create_async_engine(async_dsn, pool_pre_ping=True)
    try:
        async with AsyncSession(engine) as session:
            async with session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(a.tenant_id)})
                run_id = await create_run(
                    session, authority=a, project_id=project,
                    config_sha256="b" * 64, windows=windows,
                    budget_cap_usd=Decimal("1.000000"),
                )
        async with AsyncSession(engine) as session:
            async with session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(a.tenant_id)})
                replay = await create_run(
                    session, authority=a, project_id=project,
                    config_sha256="b" * 64, windows=windows,
                    budget_cap_usd=Decimal("1.000000"),
                )
                assert replay == run_id
                first = await reserve_call(
                    session, authority=a, run_id=run_id,
                    window_ordinal=0, idempotency_key="n4-call-0000001",
                    provider_model="test-only", estimated_max_usd="0.40",
                    period_key="2026-11",
                )
                assert first.status == "RESERVED" and not first.replay
                again = await reserve_call(
                    session, authority=a, run_id=run_id,
                    window_ordinal=0, idempotency_key="n4-call-0000001",
                    provider_model="test-only", estimated_max_usd="0.40",
                    period_key="2026-11",
                )
                assert again.replay and first.reservation_id == again.reservation_id
                with pytest.raises(N4LedgerError, match="same attempt key"):
                    await reserve_call(
                        session, authority=a, run_id=run_id, window_ordinal=0,
                        idempotency_key="n4-call-0000001", provider_model="changed-model",
                        estimated_max_usd="0.40", period_key="2026-11",
                    )

                with pytest.raises(N4BudgetError, match="unsettled"):
                    await reserve_call(
                        session, authority=a, run_id=run_id,
                        window_ordinal=0, idempotency_key="n4-call-different",
                        provider_model="test-only", estimated_max_usd="0.40",
                        period_key="2026-11",
                    )
                assert await account_call(
                    session, authority=a, reservation_id=first.reservation_id,
                    billed_usd=None,
                ) == "UNKNOWN"

        async with AsyncSession(engine) as session:
            async with session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(a.tenant_id)})
                # A retry after unknown billing cannot reserve a new model call.
                with pytest.raises(N4BudgetError, match="unsettled"):
                    await reserve_call(
                        session, authority=a, run_id=run_id,
                        window_ordinal=0, idempotency_key="n4-call-different",
                        provider_model="test-only", estimated_max_usd="0.40",
                        period_key="2026-11",
                    )
                assert await account_call(
                    session, authority=a, reservation_id=first.reservation_id,
                    billed_usd="0.30",
                ) == "SETTLED"
                assert await account_call(
                    session, authority=a, reservation_id=first.reservation_id,
                    billed_usd="0.30",
                ) == "SETTLED"
                with pytest.raises(N4LedgerError, match="differs"):
                    await account_call(
                        session, authority=a, reservation_id=first.reservation_id,
                        billed_usd="0.35",
                    )
                assert await commit_window(
                    session, authority=a, run_id=run_id, window_ordinal=0,
                    findings=[{
                        "finding_key": sha256(b"risk-one").hexdigest(),
                        "source_refs": [{"span": [10, 42], "revision": str(a.revision_id)}],
                        "claim": {"title": "Verified source candidate", "review": "PROPOSED"},
                    }],
                ) == "RUNNING"
                assert (await progress(
                    session, tenant_id=a.tenant_id, run_id=run_id,
                ))["examined_windows"] == 1
                with pytest.raises(N4LedgerError, match="different findings payload"):
                    await commit_window(
                        session, authority=a, run_id=run_id,
                        window_ordinal=0, findings=[],
                    )
                assert await session.scalar(text("""
                    SELECT candidate_state FROM public.n4_candidate_findings
                     WHERE tenant_id = CAST(:tenant AS uuid)
                       AND run_id = CAST(:run AS uuid)
                """), {"tenant": str(a.tenant_id), "run": str(run_id)}) == "PROPOSED"
                # Both tenant/project/document RUN budgets are charged once.
                balances = (await session.execute(text("""
                    SELECT scope_kind, reserved_usd, spent_usd
                      FROM public.n4_budget_buckets
                     WHERE tenant_id = CAST(:tenant AS uuid)
                """), {"tenant": str(a.tenant_id)})).mappings().all()
                assert len(balances) == 4
                assert all(Decimal(x["reserved_usd"]) == 0 for x in balances)
                assert all(Decimal(x["spent_usd"]) == Decimal("0.30") for x in balances)
                with pytest.raises(N4BudgetExceeded):
                    await reserve_call(
                        session, authority=a, run_id=run_id,
                        window_ordinal=1, idempotency_key="n4-call-too-large",
                        provider_model="test-only", estimated_max_usd="0.75",
                        period_key="2026-11",
                    )
                nxt = await reserve_call(
                    session, authority=a, run_id=run_id,
                    window_ordinal=1, idempotency_key="n4-call-0000002",
                    provider_model="test-only", estimated_max_usd="0.60",
                    period_key="2026-11",
                )
                assert await account_call(
                    session, authority=a, reservation_id=nxt.reservation_id,
                    billed_usd="0.60",
                ) == "SETTLED"
                await commit_window(
                    session, authority=a, run_id=run_id, window_ordinal=1,
                    findings=[],
                )
                current = await progress(
                    session, tenant_id=a.tenant_id, run_id=run_id,
                )
                assert current["examined_windows"] == 2
                assert current["status"] == "RUNNING"  # more than 2 windows

        # Invalid processing fence must reject writes before any budget reserve.
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("""
                UPDATE public.document_processing_operations
                   SET fencing_token = 2, attempt_id = $2, owner_token = $3
                 WHERE document_id = $1
            """, a.document_id, uuid4(), uuid4())
        finally:
            await conn.close()
        async with AsyncSession(engine) as session:
            async with session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(a.tenant_id)})
                with pytest.raises(ProcessingAuthorityLost):
                    await reserve_call(
                        session, authority=a, run_id=run_id,
                        window_ordinal=2, idempotency_key="n4-call-stale-003",
                        provider_model="test-only", estimated_max_usd="0.01",
                        period_key="2026-11",
                    )

        # An ordinary NOBYPASSRLS role cannot view other tenant's N4 rows.
        conn = await asyncpg.connect(dsn)
        role = "n4_v4_rls_probe"
        try:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=$1)", role
            )
            if not exists:
                await conn.execute(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            for table in (
                "n4_extraction_runs", "n4_extraction_windows",
                "n4_candidate_findings", "n4_budget_buckets", "n4_usage_reservations",
            ):
                await conn.execute(f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO {role}")
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {role}")
                await conn.execute(
                    "SELECT set_config('app.current_tenant',$1,true)", str(uuid4()),
                )
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.n4_extraction_runs"
                ) == 0
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.n4_candidate_findings"
                ) == 0
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.n4_budget_buckets"
                ) == 0
            async with conn.transaction():
                await conn.execute(f"SET LOCAL ROLE {role}")
                await conn.execute(
                    "SELECT set_config('app.current_tenant',$1,true)", str(a.tenant_id),
                )
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.n4_extraction_runs"
                ) == 1
                assert await conn.fetchval(
                    "SELECT count(*) FROM public.n4_candidate_findings"
                ) == 1
                assert await conn.execute(
                    "UPDATE public.n4_candidate_findings "
                    "SET candidate_state='PROPOSED'"
                ) == "UPDATE 0"
                # Even with tenant identity, the read-only candidate ledger
                # does not grant DELETE. DDL owner is the only cleanup actor.
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute(
                            "DELETE FROM public.n4_candidate_findings"
                        )
        finally:
            await conn.close()
    finally:
        await engine.dispose()



async def test_parallel_runs_cannot_oversubscribe_shared_tenant_budget():
    """Two independent project workers may spend at most the shared cap."""
    dsn = _DSN
    engine = create_async_engine(
        dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    tenant = uuid4()
    authority_a = _new_authority(tenant, uuid4(), uuid4())
    authority_b = _new_authority(tenant, uuid4(), uuid4())
    project_a, project_b = uuid4(), uuid4()
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=authority_a, project=project_a)
        await _seed_identity(
            conn, authority=authority_b, project=project_b, create_tenant=False,
        )
        await _seed_caps(
            conn, tenant, project_a, authority_a.document_id, "1.000000",
        )
        await conn.execute("""
            INSERT INTO public.n4_budget_buckets
               (tenant_id, scope_kind, scope_id, period_key, cap_usd)
            VALUES ($1, 'PROJECT', $2, '2026-11', 1),
                   ($1, 'DOCUMENT', $3, '2026-11', 1)
        """, tenant, project_b, authority_b.document_id)
    finally:
        await conn.close()

    async def new_run(a: ProcessingAuthority, project: UUID) -> UUID:
        source = ("N4 concurrent source shall be complete and valid. " * 20)
        windows = plan_n4_source_windows(
            source, revision_id=str(a.revision_id),
            max_context_chars=600, overlap_chars=50,
        )
        async with AsyncSession(engine) as session:
            async with session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(tenant)})
                return await create_run(
                    session, authority=a, project_id=project,
                    config_sha256="a" * 64, windows=windows,
                    budget_cap_usd="1",
                )

    async def take_budget(a: ProcessingAuthority, run: UUID, key: str):
        async with AsyncSession(engine) as session:
            async with session.begin():
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(tenant)})
                try:
                    reservation = await reserve_call(
                        session, authority=a, run_id=run,
                        window_ordinal=0, idempotency_key=key,
                        provider_model="test-only", estimated_max_usd="0.75",
                        period_key="2026-11",
                    )
                except N4BudgetExceeded:
                    return "DENIED"
                return reservation.status

    try:
        run_a, run_b = await asyncio.gather(
            new_run(authority_a, project_a), new_run(authority_b, project_b),
        )
        results = await asyncio.wait_for(asyncio.gather(
            take_budget(authority_a, run_a, "parallel-run-A-001"),
            take_budget(authority_b, run_b, "parallel-run-B-001"),
        ), timeout=8)
        assert sorted(results) == ["DENIED", "RESERVED"]
        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow("""
                SELECT reserved_usd, spent_usd FROM public.n4_budget_buckets
                 WHERE tenant_id=$1 AND scope_kind='TENANT'
                   AND scope_id=$1 AND period_key='2026-11'
            """, tenant)
            assert Decimal(row["reserved_usd"]) == Decimal("0.75")
            assert Decimal(row["spent_usd"]) == 0
        finally:
            await conn.close()
    finally:
        await engine.dispose()
