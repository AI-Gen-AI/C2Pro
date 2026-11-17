"""Opt-in AIService integration: real PG escrow, fake provider replies ONLY.

Proves transaction lifecycle, not LLM extraction quality or real provider use.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.analysis.adapters.ai.anthropic_client import AIService
from src.core.exceptions import AIServiceError
from tests.integration.analysis.test_legacy_shared_reservations_pg import _seed

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires migrated isolated PostgreSQL *_test"),
]


class NoRetryFakeWrapper:
    def __init__(self, *, mode="valid"):
        self.enable_cache = False
        self.cache_service = None
        self.llm_client = SimpleNamespace(max_retries=0)
        self.calls = []
        self.mode = mode

    async def generate(self, request):
        self.calls.append(request)
        if self.mode == "network_error":
            raise TimeoutError("synthetic network uncertainty")
        if self.mode == "invalid_json":
            body = '{"risk":['
        else:
            body = '{"findings":[{"status":"PROPOSED","reason":"synthetic"}]}'
        return SimpleNamespace(
            content=body,
            cost_usd=None if self.mode == "unknown_cost" else 0.16,
            input_tokens=100, output_tokens=40,
            model_used="unit-only-model", cached=False,
            latency_ms=1.0, continuations=0,
        )


def _patch_sessions(monkeypatch, engine):
    from src.core.ai import legacy_ai_governed_call as module

    @asynccontextmanager
    async def scratch_tenant(tenant_id):
        async with AsyncSession(engine) as session:
            try:
                await session.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(tenant_id)})
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(module, "get_session_with_tenant", scratch_tenant)


def _flag(monkeypatch):
    monkeypatch.setenv("C2PRO_LEGACY_AI_ESCROW", "1")
    monkeypatch.setenv("C2PRO_LEGACY_AI_RESERVE_USD", "0.30")
    monkeypatch.setenv("C2PRO_LEGACY_AI_MAX_OUTPUT_TOKENS", "2048")


async def _receipt(tenant):
    conn = await asyncpg.connect(_DSN)
    try:
        row = await conn.fetchrow("""
            SELECT status, reserved_usd, billed_usd,
                   input_tokens, output_tokens
              FROM public.legacy_ai_usage_reservations
             WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 1
        """, tenant)
        budget = await conn.fetchrow("""
            SELECT ai_spend_current, ai_spend_reserved_usd
              FROM public.tenants WHERE id=$1
        """, tenant)
        return row, budget
    finally:
        await conn.close()


@pytest.mark.parametrize("mode,accepted,expected_status", [
    ("valid", True, "SETTLED"),
    ("invalid_json", False, "SETTLED"),
    ("network_error", False, "UNKNOWN"),
    ("unknown_cost", False, "UNKNOWN"),
])
async def test_ai_service_governed_bridge_once_only(
    monkeypatch, mode, accepted, expected_status,
):
    a, _ = await _seed()
    engine = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
    )
    provider = NoRetryFakeWrapper(mode=mode)
    _patch_sessions(monkeypatch, engine)
    _flag(monkeypatch)
    service = AIService(wrapper=provider, tenant_id=a.tenant_id)
    try:
        params = {
            "system_prompt": "Project risk review in a bounded test",
            "user_content": "Untrusted source sample",
            "governed_request_id": f"bridge-{mode}-001",
        }
        if accepted:
            parsed = await service.run_extraction(**params)
            assert parsed["findings"][0]["status"] == "PROPOSED"
        else:
            with pytest.raises(AIServiceError):
                await service.run_extraction(**params)
        row, balance = await _receipt(a.tenant_id)
        assert row["status"] == expected_status
        if expected_status == "SETTLED":
            assert Decimal(row["billed_usd"]) == Decimal("0.16")
            assert row["input_tokens"] == 100
            assert balance["ai_spend_current"] == pytest.approx(0.16)
            assert balance["ai_spend_reserved_usd"] == 0
        else:
            assert row["billed_usd"] is None
            assert balance["ai_spend_current"] == 0
            assert Decimal(balance["ai_spend_reserved_usd"]) == Decimal("0.30")
        assert len(provider.calls) == 1
        # Request retry cannot call provider a second time regardless of
        # whether previous result was success, invalid, or unknown.
        with pytest.raises(AIServiceError, match="reservation"):
            await service.run_extraction(**params)
        assert len(provider.calls) == 1
    finally:
        await engine.dispose()


async def test_governed_calls_need_stable_id_and_explicit_cost_limits(monkeypatch):
    a, _ = await _seed()
    _flag(monkeypatch)
    provider = NoRetryFakeWrapper()
    service = AIService(wrapper=provider, tenant_id=a.tenant_id)
    with pytest.raises(AIServiceError, match="stable call id"):
        await service.run_extraction("system","source")
    monkeypatch.delenv("C2PRO_LEGACY_AI_RESERVE_USD")
    with pytest.raises(AIServiceError, match="explicit"):
        await service.run_extraction(
            "system","source", governed_request_id="configured-call-001",
        )
    assert provider.calls == []


async def test_governed_service_refuses_auto_retry_provider(monkeypatch):
    a, _ = await _seed()
    _flag(monkeypatch)
    provider = NoRetryFakeWrapper()
    provider.llm_client.max_retries = 3
    service = AIService(wrapper=provider, tenant_id=a.tenant_id)
    with pytest.raises(AIServiceError, match="non-retrying"):
        await service.run_extraction(
            "system", "source", governed_request_id="no-auto-retry-001",
        )
    assert provider.calls == []



async def test_concurrent_same_idempotency_key_never_sends_twice(monkeypatch):
    import asyncio

    class PausingProvider(NoRetryFakeWrapper):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def generate(self, request):
            self.started.set()
            await self.release.wait()
            return await super().generate(request)

    a, _ = await _seed()
    engine = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
    )
    provider = PausingProvider()
    _patch_sessions(monkeypatch, engine)
    _flag(monkeypatch)
    service = AIService(wrapper=provider, tenant_id=a.tenant_id)
    params = {
        "system_prompt": "bounded risk review",
        "user_content": "source",
        "governed_request_id": "same-worker-call-key-001",
    }
    first = None
    try:
        first = asyncio.create_task(service.run_extraction(**params))
        await asyncio.wait_for(provider.started.wait(), timeout=8)
        with pytest.raises(AIServiceError, match="reservation"):
            await asyncio.wait_for(service.run_extraction(**params), timeout=8)
        assert len(provider.calls) == 0
        provider.release.set()
        accepted = await asyncio.wait_for(first, timeout=8)
        assert accepted["findings"][0]["status"] == "PROPOSED"
        assert len(provider.calls) == 1
        row, balance = await _receipt(a.tenant_id)
        assert row["status"] == "SETTLED"
        assert Decimal(row["billed_usd"]) == Decimal("0.16")
        assert balance["ai_spend_reserved_usd"] == 0
    finally:
        provider.release.set()
        if first is not None:
            await first
        await engine.dispose()
