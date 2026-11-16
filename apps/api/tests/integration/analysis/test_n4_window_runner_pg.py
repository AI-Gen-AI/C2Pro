"""S2 end-to-end window runner using REAL disposable PostgreSQL and fake LLM.

This verifies transaction/authority boundaries; a mock provider response is NOT
evidence of model quality or a genuine billable model call. No production DSN.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.analysis.application.n4_incremental_runner import (
    N4IncrementalRunner,
    N4ProviderReceipt,
)
from src.analysis.domain.n4_source_windows import N4SourceWindow
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority,
    _seed_caps,
    _seed_identity,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires disposable migrated *_test database"),
]


class StubProvider:
    """Controlled responses ONLY for circuit tests; not a real provider."""

    model_name = "test-only-model"

    def __init__(self, *, error_at=None, malformed_at=None, missing_at=None):
        self.calls: list[int] = []
        self.error_at = error_at
        self.malformed_at = malformed_at
        self.missing_at = missing_at

    async def generate(
        self, *, window: N4SourceWindow, tenant_id, request_id,
    ) -> N4ProviderReceipt:
        self.calls.append(window.ordinal)
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
        period_key="2026-11", max_context_chars=600, overlap_chars=50,
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
               AND period_key='2026-11'
        """, tenant)
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
        assert first.total_windows > 1
        assert provider.calls == list(range(first.total_windows))
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["reserved_usd"]) == 0
        assert Decimal(balance["spent_usd"]) == (
            Decimal("0.02") * first.total_windows
        )
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
        assert provider.calls == [0]
        balance = await _balances(a.tenant_id)
        assert Decimal(balance["spent_usd"]) == Decimal("0.020000")
        assert Decimal(balance["reserved_usd"]) == 0
    finally:
        await engine.dispose()


async def test_unresolved_reference_keeps_candidates_proposed_and_run_partial():
    a, project, engine = await _prepare()
    provider = StubProvider(missing_at=0)
    runner = _runner(engine, provider)
    try:
        partial = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert partial.status == "PARTIAL"
        assert partial.examined_windows == partial.total_windows - 1
        conn = await asyncpg.connect(_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT status, unresolved_refs, blocked_reason
                  FROM public.n4_extraction_windows
                 WHERE tenant_id=$1 AND run_id=$2 AND ordinal=0
            """, a.tenant_id, partial.run_id)
            assert row["status"] == "BLOCKED"
            assert json.loads(row["unresolved_refs"]) == ["Annex 21 not uploaded"]
            assert row["blocked_reason"] == "REFERENCES_UNRESOLVED"
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
                estimated_max_usd="0.04", period_key="2026-11",
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

    async def no_usage(*, window, tenant_id, request_id):
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

        async def generate(self, *, window, tenant_id, request_id):
            if window.ordinal == 0:
                self.started.set()
                await self.release.wait()
            return await super().generate(
                window=window, tenant_id=tenant_id, request_id=request_id,
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
        async def generate(self, *, window, tenant_id, request_id):
            response = await super().generate(
                window=window, tenant_id=tenant_id, request_id=request_id,
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
