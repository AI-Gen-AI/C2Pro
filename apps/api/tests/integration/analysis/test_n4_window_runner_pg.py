"""S2 end-to-end window runner using REAL disposable PostgreSQL and fake LLM.

This verifies transaction/authority boundaries; a mock provider response is NOT
evidence of model quality or a genuine billable model call. No production DSN.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from decimal import Decimal

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.persistence.n4_incremental_store import (
    N4LedgerError,
    settle_unknown_pessimistically,
)
from src.analysis.application.n4_incremental_runner import (
    N4IncrementalRunner,
    N4ProviderReceipt,
)
from src.analysis.domain.n4_failure_kinds import N4CoverageStatus
from src.analysis.domain.n4_source_windows import N4SourceWindow
from src.core.processing_authority import ProcessingAuthorityLost
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _db_period,
    _new_authority,
    _seed_caps,
    _seed_identity,
)
from tests.integration.analysis.test_n4_ledger_retries_pg import _advance_generation

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires disposable migrated *_test database"),
]


class StubProvider:
    """Controlled responses ONLY for circuit tests; not a real provider."""

    model_name = "test-only-model"
    prompt_version = "n4-compact-window-v1"

    def __init__(self, *, error_at=None, malformed_at=None, missing_at=None):
        self.calls: list[int] = []
        self.attempts: list[int] = []
        self.error_at = error_at
        self.malformed_at = malformed_at
        self.missing_at = missing_at

    async def generate(
        self, *, window: N4SourceWindow, tenant_id, request_id, attempt=1,
    ) -> N4ProviderReceipt:
        self.calls.append(window.ordinal)
        self.attempts.append(attempt)
        assert tenant_id is not None and request_id
        if window.ordinal == self.error_at:
            raise TimeoutError("synthetic unknown provider receipt")
        if window.ordinal == self.malformed_at:
            content = '{"findings":['
        else:
            quote = window.context_text[: min(60, len(window.context_text))]
            payload = {
                "window_examined": True,
                "findings": [{
                    "title": f"Risk in window {window.ordinal}",
                    "category": "contractual",
                    "risk_reason": "Potential obligation to verify independently",
                    "source_quote": quote,
                    "clause_ref": f"p.{window.ordinal}",
                    "impact": "Potential delivery impact",
                }],
                "outstanding_references": (
                    ["Annex 21 not uploaded"] if window.ordinal == self.missing_at else []
                ),
            }
            content = json.dumps(payload)
        return N4ProviderReceipt(
            content=content, model_used=self.model_name,
            reported_cost_usd="0.020000", input_tokens=100, output_tokens=90,
        )


async def _prepare():
    from uuid import uuid4
    authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    conn = await asyncpg.connect(_DSN)
    try:
        await _seed_identity(conn, authority=authority, project=project)
        await _seed_caps(
            conn, authority.tenant_id, project, authority.document_id, "1.000000",
        )
    finally:
        await conn.close()
    engine = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    return authority, project, engine


def _runner(engine, provider, *, enabled=True):
    return N4IncrementalRunner(
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
        provider=provider, enabled=enabled,
        run_cap_usd=Decimal("1.000000"),
        per_window_reservation_usd=Decimal("0.040000"),
        period_key=_db_period(), max_context_chars=600, overlap_chars=50,
    )


def _source():
    return " ".join(
        f"Section {i}: The contractor shall provide a full source record "
        f"for deliverable {i}, including the relevant exceptions. "
        for i in range(11)
    )


async def _balances(tenant):
    conn = await asyncpg.connect(_DSN)
    try:
        return await conn.fetchrow("""
            SELECT reserved_usd, spent_usd FROM public.n4_budget_buckets
             WHERE tenant_id=$1 AND scope_kind='TENANT' AND scope_id=$1
               AND period_key=$2
        """, tenant, _db_period())
    finally:
        await conn.close()


async def test_successful_multiwindow_resume_never_calls_provider_twice():
    a, project, engine = await _prepare()
    provider = StubProvider()
    runner = _runner(engine, provider)
    try:
        first = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert first.status == "COMPLETE"
        assert first.examined_windows == first.total_windows
        assert first.settled_receipt_windows == first.total_windows
        assert first.persisted_result_windows == first.total_windows
        assert first.blocked_result_windows == 0
        assert first.total_windows > 1
        assert provider.calls == list(range(first.total_windows))
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == 0
        assert Decimal(balance["spent_usd"]) == (
            Decimal("0.02") * first.total_windows
        )
        conn = await asyncpg.connect(_DSN)
        try:
            usage = await conn.fetchrow("""
                SELECT sum(input_tokens) AS inputs, sum(output_tokens) AS outputs
                  FROM public.n4_usage_reservations
                 WHERE tenant_id=$1 AND run_id=$2 AND status='SETTLED'
            """, a.tenant_id, first.run_id)
            assert usage["inputs"] == 100 * first.total_windows
            assert usage["outputs"] == 90 * first.total_windows
        finally:
            await conn.close()
        second = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert second.run_id == first.run_id
        assert provider.calls == list(range(first.total_windows))
    finally:
        await engine.dispose()


async def test_provider_timeout_preserves_unknown_charge_without_recall():
    a, project, engine = await _prepare()
    provider = StubProvider(error_at=1)
    runner = _runner(engine, provider)
    try:
        partial = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert partial.status == "PARTIAL"
        assert partial.examined_windows == 1
        assert partial.stopped_reason == "PROVIDER_RESULT_UNCERTAIN"
        assert partial.settled_receipt_windows == 1
        assert partial.persisted_result_windows == 1
        assert partial.blocked_result_windows == 0
        assert provider.calls == [0, 1]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["spent_usd"]) == Decimal("0.020000")
        assert Decimal(balance["reserved_usd"]) == Decimal("0.040000")

        # Restart with same worker authority, same model and run config.
        # A blocked window is not replayed; later windows may continue.
        resumed = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert resumed.run_id == partial.run_id
        assert resumed.status == "PARTIAL"
        assert provider.calls.count(1) == 1
    finally:
        await engine.dispose()


async def test_malformed_output_is_charged_but_not_accepted_as_no_risk():
    a, project, engine = await _prepare()
    provider = StubProvider(malformed_at=0)
    runner = _runner(engine, provider)
    try:
        partial = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert partial.status == "PARTIAL"
        assert partial.examined_windows == 0
        assert partial.stopped_reason == "INVALID_PROVIDER_ENVELOPE"
        assert partial.settled_receipt_windows == 1
        assert partial.persisted_result_windows == 0
        assert partial.blocked_result_windows == 0
        assert provider.calls == [0]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["spent_usd"]) == Decimal("0.020000")
        assert Decimal(balance["reserved_usd"]) == 0
    finally:
        await engine.dispose()


async def test_unresolved_reference_keeps_candidates_proposed_without_blocking_window():
    a, project, engine = await _prepare()
    provider = StubProvider(missing_at=0)
    runner = _runner(engine, provider)
    try:
        partial = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        # JV1-A2: references no longer block; the window was examined.
        assert partial.status == "COMPLETE"
        assert partial.examined_windows == partial.total_windows
        assert partial.settled_receipt_windows == partial.total_windows
        assert partial.persisted_result_windows == partial.total_windows
        assert partial.blocked_result_windows == 0
        conn = await asyncpg.connect(_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT status, unresolved_refs, blocked_reason
                  FROM public.n4_extraction_windows
                 WHERE tenant_id=$1 AND run_id=$2 AND ordinal=0
            """, a.tenant_id, partial.run_id)
            assert row["status"] == "EXAMINED"
            assert json.loads(row["unresolved_refs"]) == ["Annex 21 not uploaded"]
            assert row["blocked_reason"] is None
            assert await conn.fetchval("""
                SELECT count(*) FROM public.n4_candidate_findings
                 WHERE tenant_id=$1 AND run_id=$2
                   AND candidate_state='PROPOSED'
            """, a.tenant_id, partial.run_id) == partial.total_windows
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_disabled_and_unattested_source_never_trigger_provider_calls():
    a, project, engine = await _prepare()
    provider = StubProvider()
    try:
        with pytest.raises(PermissionError, match="disabled"):
            await _runner(engine, provider, enabled=False).run(
                authority=a, project_id=project,
                model_safe_text=_source(), n2_projection_attested=True,
            )
        with pytest.raises(PermissionError, match="N2-safe"):
            await _runner(engine, provider).run(
                authority=a, project_id=project,
                model_safe_text=_source(), n2_projection_attested=False,
            )
        assert provider.calls == []
    finally:
        await engine.dispose()



async def test_persisted_reservation_replay_is_blocked_without_provider_call():
    """Even a crash before send must never authorize a second send."""
    from hashlib import sha256

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.analysis.adapters.persistence.n4_incremental_store import (
        create_run,
        reserve_call,
    )
    from src.analysis.domain.n4_source_windows import plan_n4_source_windows

    a, project, engine = await _prepare()
    provider = StubProvider()
    runner = _runner(engine, provider)
    try:
        windows = plan_n4_source_windows(
            _source(), revision_id=str(a.revision_id),
            max_context_chars=600, overlap_chars=50,
        )
        config = {
            "prompt": "n4-compact-window-v1",
            "model": provider.model_name, "window_chars": 600, "overlap": 50,
        }
        digest = sha256(json.dumps(
            config, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.current_tenant', :tenant, true)"
            ), {"tenant": str(a.tenant_id)})
            run_id = await create_run(
                session, authority=a, project_id=project,
                config_sha256=digest, windows=windows,
                budget_cap_usd="1",
            )
            call_key = sha256(
                f"n4:{run_id}:0:{windows[0].context_sha256}:"
                f"{provider.model_name}".encode()
            ).hexdigest()
            reserved = await reserve_call(
                session, authority=a, run_id=run_id, window_ordinal=0,
                idempotency_key=call_key, provider_model=provider.model_name,
                estimated_max_usd="0.04", period_key=_db_period(),
            )
            assert not reserved.replay

        outcome = await runner.run(
            authority=a, project_id=project, model_safe_text=_source(),
            n2_projection_attested=True,
        )
        assert outcome.run_id == run_id
        assert outcome.status == "PREPARING"
        assert outcome.stopped_reason == (
            "EXISTING_RESERVATION_REQUIRES_RECONCILIATION"
        )
        assert provider.calls == []
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == Decimal("0.040000")
        assert Decimal(balance["spent_usd"]) == 0
    finally:
        await engine.dispose()


async def test_missing_budget_cap_pauses_without_sending_to_provider():
    a, project, engine = await _prepare()
    provider = StubProvider()
    try:
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("""
                UPDATE public.n4_budget_buckets SET cap_usd=0.01
                 WHERE tenant_id=$1 AND scope_kind='TENANT'
            """, a.tenant_id)
        finally:
            await conn.close()
        outcome = await _runner(engine, provider).run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert outcome.status == "PARTIAL"
        assert outcome.stopped_reason == "N4BudgetExceeded"
        assert outcome.examined_windows == 0
        assert provider.calls == []
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["spent_usd"]) == 0
        assert Decimal(balance["reserved_usd"]) == 0
    finally:
        await engine.dispose()


async def test_no_cost_receipt_is_not_zero_and_does_not_validate_findings():
    a, project, engine = await _prepare()
    provider = StubProvider()

    async def no_usage(*, window, tenant_id, request_id, attempt=1):
        provider.calls.append(window.ordinal)
        return N4ProviderReceipt(
            content='{"window_examined":true,"findings":[],'
                    '"outstanding_references":[]}',
            model_used=provider.model_name, reported_cost_usd=None,
            input_tokens=0, output_tokens=0,
        )

    provider.generate = no_usage
    try:
        outcome = await _runner(engine, provider).run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert outcome.status == "PARTIAL"
        assert outcome.stopped_reason == "USAGE_UNAVAILABLE"
        assert outcome.examined_windows == 0
        assert provider.calls == [0]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == Decimal("0.04")
        assert Decimal(balance["spent_usd"]) == 0
    finally:
        await engine.dispose()



async def test_simultaneous_runners_replay_does_not_interrupt_inflight_provider():
    """Second worker cannot send twice or block the first worker's commit."""
    import asyncio

    class PausingProvider(StubProvider):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def generate(self, *, window, tenant_id, request_id, attempt=1):
            if window.ordinal == 0:
                self.started.set()
                await self.release.wait()
            return await super().generate(
                window=window, tenant_id=tenant_id, request_id=request_id,
                attempt=attempt,
            )

    a, project, engine = await _prepare()
    provider = PausingProvider()
    runner = _runner(engine, provider)
    try:
        first_task = asyncio.create_task(runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        ))
        await asyncio.wait_for(provider.started.wait(), timeout=8)
        replay = await asyncio.wait_for(runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        ), timeout=8)
        assert replay.stopped_reason == (
            "EXISTING_RESERVATION_REQUIRES_RECONCILIATION"
        )
        assert not first_task.done() and provider.calls == []
        provider.release.set()
        first = await asyncio.wait_for(first_task, timeout=12)
        assert first.status == "COMPLETE"
        assert first.examined_windows == first.total_windows
        assert provider.calls == list(range(first.total_windows))
    finally:
        provider.release.set()
        await engine.dispose()



async def test_invalid_pricing_receipt_is_unknown_not_zero():
    from dataclasses import replace

    a, project, engine = await _prepare()

    class InvalidCostProvider(StubProvider):
        async def generate(self, *, window, tenant_id, request_id, attempt=1):
            response = await super().generate(
                window=window, tenant_id=tenant_id, request_id=request_id,
                attempt=attempt,
            )
            return replace(response, reported_cost_usd="not-a-price")

    provider = InvalidCostProvider()
    try:
        outcome = await _runner(engine, provider).run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert outcome.status == "PARTIAL"
        assert outcome.stopped_reason == "USAGE_UNAVAILABLE"
        assert provider.calls == [0]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == Decimal("0.04")
        assert Decimal(balance["spent_usd"]) == 0
    finally:
        await engine.dispose()


async def test_a3_paid_invalid_envelope_retries_with_distinct_ledger_keys():
    a, project, engine = await _prepare()
    provider = StubProvider(malformed_at=0)
    runner = _runner(engine, provider)
    try:
        first = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert first.status == "PARTIAL" and first.gap_windows == (0,)
        assert first.coverage_status is N4CoverageStatus.INCOMPLETE
        provider.malformed_at = None
        resumed = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert resumed.run_id == first.run_id
        assert resumed.status == "COMPLETE"
        assert resumed.examined_windows == resumed.total_windows
        assert resumed.gap_windows == ()
        assert resumed.coverage_status is N4CoverageStatus.COMPLETE
        assert provider.calls == [0, *range(resumed.total_windows)]
        assert provider.attempts == [1, 2, *([1] * (resumed.total_windows - 1))]
        conn = await asyncpg.connect(_DSN)
        try:
            receipts = await conn.fetch("""
                SELECT status, spent_usd, idempotency_key
                  FROM public.n4_usage_reservations
                 WHERE tenant_id=$1 AND run_id=$2 AND window_ordinal=0
                 ORDER BY created_at
            """, a.tenant_id, resumed.run_id)
            assert len(receipts) == 2
            assert all(row["status"] == "SETTLED" for row in receipts)
            assert len({row["idempotency_key"] for row in receipts}) == 2
            assert [Decimal(row["spent_usd"]) for row in receipts] == [
                Decimal("0.02"), Decimal("0.02"),
            ]
        finally:
            await conn.close()
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == 0
        assert Decimal(balance["spent_usd"]) == Decimal("0.02") * (
            resumed.total_windows + 1
        )
    finally:
        await engine.dispose()


async def test_a3_unknown_requires_explicit_settlement_before_retry():
    a, project, engine = await _prepare()
    provider = StubProvider(error_at=0)
    runner = _runner(engine, provider)
    try:
        first = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert first.status == "PARTIAL" and first.gap_windows == (0,)
        provider.error_at = None
        paused = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert paused.run_id == first.run_id
        assert paused.stopped_reason == "OPEN_LIABILITY_REQUIRES_RECONCILIATION"
        assert provider.calls == [0]
        conn = await asyncpg.connect(_DSN)
        try:
            receipt = await conn.fetchrow("""
                SELECT reservation_id, status FROM public.n4_usage_reservations
                 WHERE tenant_id=$1 AND run_id=$2
            """, a.tenant_id, first.run_id)
            assert receipt["status"] == "UNKNOWN"
            reservation_id = receipt["reservation_id"]
        finally:
            await conn.close()
        async with AsyncSession(engine) as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(a.tenant_id)},
            )
            charged = await settle_unknown_pessimistically(
                session, authority=a, reservation_id=reservation_id,
                actual_provider="anthropic", reason="synthetic reconciled liability",
            )
        assert charged == Decimal("0.040000")
        resumed = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert resumed.run_id == first.run_id and resumed.status == "COMPLETE"
        assert resumed.coverage_status is N4CoverageStatus.COMPLETE
        assert provider.calls == [0, 0, *range(1, resumed.total_windows)]
        assert provider.attempts[:2] == [1, 2]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == 0
        assert Decimal(balance["spent_usd"]) == (
            Decimal("0.04") + Decimal("0.02") * resumed.total_windows
        )
    finally:
        await engine.dispose()


async def test_a3_retry_cap_keeps_gap_instead_of_unbounded_charges():
    a, project, engine = await _prepare()
    provider = StubProvider(malformed_at=0)
    runner = N4IncrementalRunner(
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
        provider=provider, enabled=True, run_cap_usd="1",
        per_window_reservation_usd="0.04", period_key=_db_period(),
        max_context_chars=600, overlap_chars=50, max_attempts=2,
    )
    try:
        for _ in range(2):
            outcome = await runner.run(
                authority=a, project_id=project,
                model_safe_text=_source(), n2_projection_attested=True,
            )
            assert outcome.status == "PARTIAL" and outcome.gap_windows == (0,)
        last = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert last.status == "PARTIAL"
        assert last.examined_windows == last.total_windows - 1
        assert last.coverage_status is N4CoverageStatus.COMPLETE_WITH_GAPS
        assert last.gap_windows == (0,)
        assert provider.calls == [0, 0, *range(1, last.total_windows)]
        assert provider.attempts[:2] == [1, 2]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == 0
        assert Decimal(balance["spent_usd"]) == (
            Decimal("0.04") + Decimal("0.02") * (last.total_windows - 1)
        )
    finally:
        await engine.dispose()


async def test_a3_v2_config_never_reuses_v1_source_results():
    a, project, engine = await _prepare()
    v1, v2 = StubProvider(), StubProvider()
    v2.prompt_version = "n4-compact-window-v2"
    original_runner, changed_runner = _runner(engine, v1), _runner(engine, v2)
    assert original_runner.config_sha256 != changed_runner.config_sha256
    try:
        original = await original_runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert original.status == "COMPLETE"
        before = await _balances(a.tenant_id)
        changed = await changed_runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert changed.run_id != original.run_id
        assert changed.status == "PARTIAL"
        assert changed.stopped_reason == "N4PriorRunReconciliationRequired"
        assert changed.examined_windows == 0 and changed.gap_windows == (0,)
        assert v2.calls == []
        assert await _balances(a.tenant_id) == before
    finally:
        await engine.dispose()


async def test_a3_new_generation_adopts_preparing_run_and_fences_old_worker():
    class PausingProvider(StubProvider):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def generate(self, *, window, tenant_id, request_id, attempt=1):
            self.started.set()
            await self.release.wait()
            return await super().generate(
                window=window, tenant_id=tenant_id,
                request_id=request_id, attempt=attempt,
            )

    a, project, engine = await _prepare()
    provider = PausingProvider()
    runner = _runner(engine, provider)
    task = asyncio.create_task(runner.run(
        authority=a, project_id=project,
        model_safe_text=_source(), n2_projection_attested=True,
    ))
    try:
        await asyncio.wait_for(provider.started.wait(), timeout=10)
        a2 = await _advance_generation(a)
        provider.release.set()
        with pytest.raises((ProcessingAuthorityLost, N4LedgerError)):
            await asyncio.wait_for(task, timeout=15)
        before = await _balances(a.tenant_id)
        assert Decimal(before["reserved_usd"]) == Decimal("0.04")
        resumed = await _runner(engine, provider).run(
            authority=a2, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert resumed.stopped_reason == "EXISTING_RESERVATION_REQUIRES_RECONCILIATION"
        assert resumed.examined_windows == 0
        assert resumed.status == "PREPARING"
        assert provider.calls == [0]
        assert await _balances(a.tenant_id) == before
        conn = await asyncpg.connect(_DSN)
        try:
            runs = await conn.fetch("""
                SELECT run_id, generation, fencing_token
                  FROM public.n4_extraction_runs
                 WHERE tenant_id=$1 ORDER BY created_at
            """, a.tenant_id)
            assert len(runs) == 1
            assert runs[0]["run_id"] == resumed.run_id
            assert (runs[0]["generation"], runs[0]["fencing_token"]) == (2, 2)
        finally:
            await conn.close()
    finally:
        provider.release.set()
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await engine.dispose()
