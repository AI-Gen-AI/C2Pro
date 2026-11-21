"""JV1-A2: N4 ledger retries, non-blocking references, run adoption and
explicit pessimistic settlement — real PostgreSQL, scratch-only.

Requires C2PRO_N4_SCRATCH_DSN ending in *_test, upgraded with Alembic.
Never calls a provider; all amounts and text are synthetic.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import replace
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
    N4LedgerError,
    N4PriorRunReconciliationRequired,
    account_call,
    block_window,
    commit_window,
    create_run,
    progress,
    reserve_call,
    retryable_windows,
    settle_unknown_pessimistically,
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

_PERIOD = "2026-11"
_CONFIG = "b" * 64
_SOURCE = "The Contractor shall comply with clause 9.6 and Annex 4. " * 30


def _authority(tenant: UUID, document: UUID, revision: UUID) -> ProcessingAuthority:
    return ProcessingAuthority(
        tenant_id=tenant, document_id=document, revision_id=revision,
        generation=1, stage=ProcessingStage.ANALYSIS, attempt_id=uuid4(),
        owner_token=uuid4(), fencing_token=1,
    )


async def _seed(a: ProcessingAuthority, project: UUID, cap: str = "1.000000") -> None:
    conn = await asyncpg.connect(_DSN)
    try:
        await conn.execute("SELECT set_config('app.current_tenant', $1, false)", str(a.tenant_id))
        await conn.execute("""
            INSERT INTO public.tenants (id, name, slug, subscription_plan,
                                        ai_budget_monthly, ai_spend_last_reset)
            VALUES ($1, 'N4 A2 scratch tenant', $2, 'free', 10, clock_timestamp())
        """, a.tenant_id, f"n4-a2-{a.tenant_id.hex}")
        await conn.execute("""
            INSERT INTO public.projects (id, tenant_id, name, project_type, status)
            VALUES ($1, $2, 'N4 A2 scratch', 'construction', 'active')
        """, project, a.tenant_id)
        await conn.execute("""
            INSERT INTO public.documents (id, project_id, tenant_id, filename, document_type)
            VALUES ($1, $2, $3, 'synthetic-contract.pdf', 'contract')
        """, a.document_id, project, a.tenant_id)
        await conn.execute("""
            INSERT INTO public.document_revisions
              (revision_id, document_id, project_id, tenant_id, rev_no,
               blob_hash, blob_key, valid_from)
            VALUES ($1, $2, $3, $4, 1, $5, 'scratch/source', clock_timestamp())
        """, a.revision_id, a.document_id, project, a.tenant_id, "a" * 64)
        await conn.execute("""
            INSERT INTO public.document_processing_operations
              (document_id, tenant_id, revision_id, generation, stage, phase,
               attempt_id, owner_token, fencing_token, lease_expires_at)
            VALUES ($1, $2, $3, 1, 'ANALYSIS', 'RUNNING',
                    $4, $5, 1, clock_timestamp() + interval '1 hour')
        """, a.document_id, a.tenant_id, a.revision_id, a.attempt_id, a.owner_token)
        for kind, scope in (
            ("TENANT", a.tenant_id), ("PROJECT", project), ("DOCUMENT", a.document_id),
        ):
            await conn.execute("""
                INSERT INTO public.n4_budget_buckets
                  (tenant_id, scope_kind, scope_id, period_key, cap_usd)
                VALUES ($1, $2, $3, $4, $5)
            """, a.tenant_id, kind, scope, _PERIOD, Decimal(cap))
    finally:
        await conn.close()


async def _advance_generation(a: ProcessingAuthority) -> ProcessingAuthority:
    new = replace(
        a, generation=a.generation + 1, fencing_token=a.fencing_token + 1,
        attempt_id=uuid4(), owner_token=uuid4(),
    )
    conn = await asyncpg.connect(_DSN)
    try:
        await conn.execute("""
            UPDATE public.document_processing_operations
               SET generation=$2, fencing_token=$3, phase='RUNNING',
                   attempt_id=$4, owner_token=$5,
                   lease_expires_at=clock_timestamp()+interval '1 hour'
             WHERE document_id=$1
        """, a.document_id, new.generation, new.fencing_token,
            new.attempt_id, new.owner_token)
    finally:
        await conn.close()
    return new


def _windows(a: ProcessingAuthority):
    windows = plan_n4_source_windows(
        _SOURCE, revision_id=str(a.revision_id),
        max_context_chars=600, overlap_chars=50,
    )
    assert len(windows) >= 2
    return windows


def _finding(label: str, a: ProcessingAuthority) -> dict:
    return {
        "finding_key": sha256(label.encode()).hexdigest(),
        "source_refs": [{"span": [10, 42], "revision": str(a.revision_id)}],
        "claim": {"title": f"Synthetic {label}", "review": "PROPOSED"},
    }


@asynccontextmanager
async def _tx(engine, a: ProcessingAuthority, *, commit: bool = True):
    """One tenant-scoped transaction; commit only when asked and no error."""
    async with AsyncSession(engine) as session:
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(a.tenant_id)},
        )
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        if commit:
            await session.commit()
        else:
            await session.rollback()


async def _reserve(session, a, run_id, ordinal, key, amount="0.100000"):
    return await reserve_call(
        session, authority=a, run_id=run_id, window_ordinal=ordinal,
        idempotency_key=key, provider_model="synthetic-model",
        estimated_max_usd=amount, period_key=_PERIOD,
    )


async def _balances(a: ProcessingAuthority) -> tuple[list[dict], dict]:
    conn = await asyncpg.connect(_DSN)
    try:
        buckets = [dict(r) for r in await conn.fetch("""
            SELECT scope_kind, reserved_usd, spent_usd FROM public.n4_budget_buckets
             WHERE tenant_id=$1
        """, a.tenant_id)]
        tenant = dict(await conn.fetchrow("""
            SELECT ai_spend_reserved_usd, ai_spend_current FROM public.tenants WHERE id=$1
        """, a.tenant_id))
        return buckets, tenant
    finally:
        await conn.close()


async def _window_row(a: ProcessingAuthority, run_id: UUID, ordinal: int) -> dict:
    conn = await asyncpg.connect(_DSN)
    try:
        return dict(await conn.fetchrow("""
            SELECT status, blocked_reason, unresolved_refs, findings_sha256
              FROM public.n4_extraction_windows
             WHERE tenant_id=$1 AND run_id=$2 AND ordinal=$3
        """, a.tenant_id, run_id, ordinal))
    finally:
        await conn.close()


@pytest.fixture
async def engine():
    eng = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1), pool_pre_ping=True,
    )
    yield eng
    await eng.dispose()


async def _new_run(engine, a, project, config=_CONFIG):
    async with _tx(engine, a) as s:
        run_id = await create_run(
            s, authority=a, project_id=project, config_sha256=config,
            windows=_windows(a), budget_cap_usd="1.000000",
        )
    return run_id


# --- acceptance (1): retry sums both attempts and releases every hold -------


async def test_retry_after_failed_attempt_sums_spend_and_releases_holds(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)

    async with _tx(engine, a) as s:
        first = await _reserve(s, a, run_id, 0, "a2-attempt-0001")
        assert await account_call(
            s, authority=a, reservation_id=first.reservation_id, billed_usd="0.020000",
        ) == "SETTLED"
        await block_window(s, authority=a, run_id=run_id, window_ordinal=0,
                           reason="INVALID_ENVELOPE")
        assert await retryable_windows(
            s, tenant_id=a.tenant_id, run_id=run_id, max_attempts=3,
        ) == (0,)
        assert await retryable_windows(
            s, tenant_id=a.tenant_id, run_id=run_id, max_attempts=1,
        ) == ()

    async with _tx(engine, a) as s:
        second = await _reserve(s, a, run_id, 0, "a2-attempt-0002")
        assert second.status == "RESERVED" and not second.replay
    # The retry reopens the window; while it is in flight it is not retryable.
    assert (await _window_row(a, run_id, 0))["status"] == "PENDING"

    async with _tx(engine, a, commit=False) as s:
        assert await retryable_windows(
            s, tenant_id=a.tenant_id, run_id=run_id, max_attempts=3,
        ) == ()
        # Nothing can be examined while the current attempt is unsettled.
        with pytest.raises(N4LedgerError, match="unsettled"):
            await commit_window(
                s, authority=a, run_id=run_id, window_ordinal=0,
                findings=[_finding("retry", a)],
            )

    async with _tx(engine, a) as s:
        assert await account_call(
            s, authority=a, reservation_id=second.reservation_id, billed_usd="0.030000",
        ) == "SETTLED"
        assert await commit_window(
            s, authority=a, run_id=run_id, window_ordinal=0,
            findings=[_finding("retry", a)],
        ) == "RUNNING"

    assert (await _window_row(a, run_id, 0))["status"] == "EXAMINED"
    buckets, tenant = await _balances(a)
    assert len(buckets) == 4
    assert all(Decimal(b["reserved_usd"]) == 0 for b in buckets)
    assert all(Decimal(b["spent_usd"]) == Decimal("0.05") for b in buckets)
    assert Decimal(str(tenant["ai_spend_reserved_usd"])) == 0
    assert Decimal(str(tenant["ai_spend_current"])) == Decimal("0.05")


async def test_window_with_committed_result_is_neither_retryable_nor_reservable(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    async with _tx(engine, a, commit=False) as s:
        first = await _reserve(s, a, run_id, 0, "a2-result-0001")
        await account_call(s, authority=a, reservation_id=first.reservation_id,
                           billed_usd="0.010000")
        assert await commit_window(
            s, authority=a, run_id=run_id, window_ordinal=0,
            findings=[_finding("partial", a)],
            incomplete_reason="MODEL_DID_NOT_EXAMINE_WINDOW",
        ) == "PARTIAL"
        assert await retryable_windows(
            s, tenant_id=a.tenant_id, run_id=run_id, max_attempts=3,
        ) == ()
        with pytest.raises(N4LedgerError, match="committed result"):
            await _reserve(s, a, run_id, 0, "a2-result-0002")


# --- non-blocking references -----------------------------------------------


async def test_unresolved_references_are_stored_without_blocking_the_window(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    async with _tx(engine, a) as s:
        first = await _reserve(s, a, run_id, 0, "a2-refs-00001")
        await account_call(s, authority=a, reservation_id=first.reservation_id,
                           billed_usd="0.010000")
        assert await commit_window(
            s, authority=a, run_id=run_id, window_ordinal=0,
            findings=[_finding("refs", a)],
            unresolved_refs=("Annex 4 not supplied",),
        ) == "RUNNING"
        current = await progress(s, tenant_id=a.tenant_id, run_id=run_id)
        assert current["examined_windows"] == 1
    row = await _window_row(a, run_id, 0)
    assert row["status"] == "EXAMINED"
    assert row["blocked_reason"] is None
    assert row["unresolved_refs"] == '["Annex 4 not supplied"]'


# --- acceptance (3): UNKNOWN only released by explicit pessimistic settlement


async def test_unknown_is_released_only_by_explicit_pessimistic_settlement(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    async with _tx(engine, a) as s:
        first = await _reserve(s, a, run_id, 0, "a2-unknown-001", amount="0.100000")
        assert await account_call(
            s, authority=a, reservation_id=first.reservation_id, billed_usd=None,
        ) == "UNKNOWN"
        await block_window(s, authority=a, run_id=run_id, window_ordinal=0,
                           reason="PROVIDER_RESULT_UNCERTAIN")

    async with _tx(engine, a, commit=False) as s:
        assert await retryable_windows(
            s, tenant_id=a.tenant_id, run_id=run_id, max_attempts=3,
        ) == ()
        with pytest.raises(N4BudgetError, match="unsettled"):
            await _reserve(s, a, run_id, 0, "a2-unknown-002")

    # A new generation adopting the run does not forgive the UNKNOWN charge.
    a2 = await _advance_generation(a)
    assert await _new_run(engine, a2, project) == run_id
    _, tenant = await _balances(a)
    assert Decimal(str(tenant["ai_spend_reserved_usd"])) == Decimal("0.1")

    async with _tx(engine, a2) as s:
        with pytest.raises(ValueError, match="reason"):
            await settle_unknown_pessimistically(
                s, authority=a2, reservation_id=first.reservation_id,
                actual_provider="anthropic", reason=" ",
            )
        charged = await settle_unknown_pessimistically(
            s, authority=a2, reservation_id=first.reservation_id,
            actual_provider="anthropic", reason="operator: provider receipt never arrived",
        )
        assert charged == Decimal("0.100000")
        with pytest.raises(N4LedgerError, match="UNKNOWN"):
            await settle_unknown_pessimistically(
                s, authority=a2, reservation_id=first.reservation_id,
                actual_provider="anthropic", reason="operator: second attempt",
            )
        assert await retryable_windows(
            s, tenant_id=a.tenant_id, run_id=run_id, max_attempts=3,
        ) == (0,)

    buckets, tenant = await _balances(a)
    assert all(Decimal(b["reserved_usd"]) == 0 for b in buckets)
    assert all(Decimal(b["spent_usd"]) == Decimal("0.1") for b in buckets)
    assert Decimal(str(tenant["ai_spend_reserved_usd"])) == 0
    assert Decimal(str(tenant["ai_spend_current"])) == Decimal("0.1")


async def test_pessimistic_settlement_refuses_reserved_attempt(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    async with _tx(engine, a, commit=False) as s:
        first = await _reserve(s, a, run_id, 0, "a2-inflight-01")
        with pytest.raises(N4LedgerError, match="UNKNOWN"):
            await settle_unknown_pessimistically(
                s, authority=a, reservation_id=first.reservation_id,
                actual_provider="anthropic", reason="operator: in flight",
            )


# --- acceptance (2): adoption by a new generation ---------------------------


async def test_new_generation_with_same_config_adopts_run_without_rereserving(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    async with _tx(engine, a) as s:
        w0 = await _reserve(s, a, run_id, 0, "a2-adopt-w0-01")
        await account_call(s, authority=a, reservation_id=w0.reservation_id,
                           billed_usd="0.020000")
        await commit_window(s, authority=a, run_id=run_id, window_ordinal=0,
                            findings=[_finding("w0", a)])
        w1 = await _reserve(s, a, run_id, 1, "a2-adopt-w1-01")
        await account_call(s, authority=a, reservation_id=w1.reservation_id,
                           billed_usd="0.020000")
        await block_window(s, authority=a, run_id=run_id, window_ordinal=1,
                           reason="OUTPUT_TRUNCATED")

    a2 = await _advance_generation(a)
    assert await _new_run(engine, a2, project) == run_id
    conn = await asyncpg.connect(_DSN)
    try:
        run = await conn.fetchrow("""
            SELECT generation, fencing_token, status FROM public.n4_extraction_runs
             WHERE tenant_id=$1 AND run_id=$2
        """, a.tenant_id, run_id)
    finally:
        await conn.close()
    assert (run["generation"], run["fencing_token"]) == (2, 2)
    assert run["status"] == "PARTIAL"

    async with _tx(engine, a2, commit=False) as s:
        with pytest.raises(N4LedgerError, match="examined"):
            await _reserve(s, a2, run_id, 0, "a2-adopt-w0-02")

    async with _tx(engine, a2) as s:
        retry = await _reserve(s, a2, run_id, 1, "a2-adopt-w1-02")
        assert retry.status == "RESERVED"

    # The previous generation is fenced out of the adopted run.
    async with _tx(engine, a, commit=False) as s:
        with pytest.raises((ProcessingAuthorityLost, N4LedgerError)):
            await _reserve(s, a, run_id, 2, "a2-adopt-stale-1")

    buckets, _ = await _balances(a)
    run_bucket = next(b for b in buckets if b["scope_kind"] == "RUN")
    assert Decimal(run_bucket["spent_usd"]) == Decimal("0.04")


async def test_new_generation_with_different_config_stays_blocked(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    async with _tx(engine, a) as s:
        w0 = await _reserve(s, a, run_id, 0, "a2-config-w0-1")
        await account_call(s, authority=a, reservation_id=w0.reservation_id,
                           billed_usd="0.020000")
        await block_window(s, authority=a, run_id=run_id, window_ordinal=0,
                           reason="INVALID_ENVELOPE")

    a2 = await _advance_generation(a)
    other = await _new_run(engine, a2, project, config="c" * 64)
    assert other != run_id
    async with _tx(engine, a2, commit=False) as s:
        with pytest.raises(N4PriorRunReconciliationRequired):
            await _reserve(s, a2, other, 0, "a2-config-w0-2")


async def test_complete_run_is_never_adopted(engine):
    a, project = _authority(uuid4(), uuid4(), uuid4()), uuid4()
    await _seed(a, project)
    run_id = await _new_run(engine, a, project)
    total = len(_windows(a))
    async with _tx(engine, a) as s:
        for ordinal in range(total):
            r = await _reserve(s, a, run_id, ordinal, f"a2-complete-{ordinal:04d}",
                               amount="0.010000")
            await account_call(s, authority=a, reservation_id=r.reservation_id,
                               billed_usd="0.001000")
            status = await commit_window(s, authority=a, run_id=run_id,
                                         window_ordinal=ordinal,
                                         findings=[_finding(f"c{ordinal}", a)])
        assert status == "COMPLETE"
    a2 = await _advance_generation(a)
    assert await _new_run(engine, a2, project) != run_id
