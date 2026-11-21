"""Real scratch PostgreSQL proof: N4 direct fallback charges the actual model.

No provider network calls. The existing authoritative run/window ledger and
the real transaction boundaries are exercised with a stub response.
"""
from __future__ import annotations

import os
from decimal import Decimal

import asyncpg
import pytest

from src.analysis.application.n4_incremental_runner import (
    N4ProviderReceipt,
)
from src.core.ai.direct_provider_fallback import DirectRoute
from tests.integration.analysis.test_n4_window_runner_pg import (
    StubProvider,
    _prepare,
    _runner,
    _source,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires disposable migrated *_test PostgreSQL"),
]


class FallbackResultProvider(StubProvider):
    model_name = "claude-sonnet-4-6"
    approved_fallback_models = frozenset({"gpt-4.1"})
    fallback_reservation_usd = Decimal("0.040000")
    fallback_routes = (
        DirectRoute(
            provider="openai", model="gpt-4.1",
            context_tokens=200000, output_tokens=32000,
            input_usd_m=Decimal("2"), output_usd_m=Decimal("8"),
        ),
    )

    async def generate(self, *, window, tenant_id, request_id):
        base = await super().generate(
            window=window, tenant_id=tenant_id, request_id=request_id,
        )
        return N4ProviderReceipt(
            content=base.content, model_used="gpt-4.1",
            reported_cost_usd="0.020000", input_tokens=100,
            output_tokens=90, provider_request_id=request_id,
        )


async def test_n4_reserved_anthropic_settles_openai_actual_model_and_no_double_spend():
    a, project, engine = await _prepare()
    provider = FallbackResultProvider()
    runner = _runner(engine, provider)
    try:
        first = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert first.status == "COMPLETE"
        assert first.settled_receipt_windows == first.total_windows
        assert first.persisted_result_windows == first.total_windows
        count_before = len(provider.calls)

        async with asyncpg.create_pool(_DSN) as pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, false)",
                    str(a.tenant_id),
                )
                records = await conn.fetch("""
                    SELECT model_name, actual_model_name, actual_provider, spent_usd
                    FROM public.n4_usage_reservations
                    WHERE tenant_id=$1 AND status='SETTLED'
                """, a.tenant_id)
                assert len(records) == first.total_windows
                assert all(row["model_name"] == "claude-sonnet-4-6" for row in records)
                assert all(row["actual_model_name"] == "gpt-4.1" for row in records)
                assert all(row["actual_provider"] == "openai" for row in records)
                assert all(Decimal(row["spent_usd"]) == Decimal("0.020000") for row in records)

        second = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert second.status == "COMPLETE"
        assert len(provider.calls) == count_before
    finally:
        await engine.dispose()


async def test_n4_declines_fallback_if_reservation_cap_does_not_match():
    a, project, engine = await _prepare()
    try:
        provider = FallbackResultProvider()
        provider.fallback_reservation_usd = Decimal("0.050000")
        with pytest.raises(ValueError, match="actual per-window"):
            _runner(engine, provider)
    finally:
        await engine.dispose()


async def test_n4_partial_billable_fallback_settles_actual_provider_but_not_findings():
    from src.core.ai.llm_client import LLMPartialGenerationError

    class PartialProvider(FallbackResultProvider):
        async def generate(self, *, window, tenant_id, request_id):
            self.calls.append(window.ordinal)
            raise LLMPartialGenerationError(
                "output truncated after charge",
                model="gpt-4.1", input_tokens=101,
                output_tokens=25, cost_usd=0.012345,
            )

    a, project, engine = await _prepare()
    runner = _runner(engine, PartialProvider())
    try:
        result = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert result.stopped_reason == "PROVIDER_RESULT_UNCERTAIN"
        assert result.persisted_result_windows == 0
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, false)",
                str(a.tenant_id),
            )
            row = await conn.fetchrow("""
                SELECT status, spent_usd, actual_model_name,
                       actual_provider, input_tokens, output_tokens
                FROM public.n4_usage_reservations
                WHERE tenant_id=$1
            """, a.tenant_id)
            assert row["status"] == "SETTLED"
            assert row["spent_usd"] == Decimal("0.012345")
            assert row["actual_model_name"] == "gpt-4.1"
            assert row["actual_provider"] == "openai"
            assert row["input_tokens"] == 101
            assert row["output_tokens"] == 25
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_unknown_billable_model_keeps_ledger_unknown_instead_of_fabricating_anthropic_charge():
    from src.core.ai.llm_client import LLMPartialGenerationError

    class UnknownModelProvider(FallbackResultProvider):
        async def generate(self, *, window, tenant_id, request_id):
            self.calls.append(window.ordinal)
            raise LLMPartialGenerationError(
                "unknown direct-provider output billed",
                model="undocumented-provider-model",
                input_tokens=100, output_tokens=25, cost_usd=0.012,
            )

    a, project, engine = await _prepare()
    runner = _runner(engine, UnknownModelProvider())
    try:
        result = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert result.stopped_reason == "PROVIDER_RESULT_UNCERTAIN"
        assert result.persisted_result_windows == 0
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, false)",
                str(a.tenant_id),
            )
            row = await conn.fetchrow("""
                SELECT status, spent_usd, actual_model_name, actual_provider
                FROM public.n4_usage_reservations
                WHERE tenant_id=$1
            """, a.tenant_id)
            assert row["status"] == "UNKNOWN"
            assert row["spent_usd"] is None
            assert row["actual_model_name"] is None
            assert row["actual_provider"] is None
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_n4_direct_openai_primary_settles_openai_not_anthropic():
    """Direct provider is primary, not a fallback from Anthropic."""
    class OpenAIPrimary(StubProvider):
        model_name = "gpt-4.1"
        provider_name = "openai"

    a, project, engine = await _prepare()
    provider = OpenAIPrimary()
    runner = _runner(engine, provider)
    try:
        result = await runner.run(
            authority=a, project_id=project,
            model_safe_text=_source(), n2_projection_attested=True,
        )
        assert result.status == "COMPLETE"
        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute("SELECT set_config('app.current_tenant',$1,false)", str(a.tenant_id))
            rows = await conn.fetch("""
                SELECT model_name,actual_model_name,actual_provider,spent_usd
                FROM public.n4_usage_reservations
                WHERE tenant_id=$1 ORDER BY window_ordinal
            """,a.tenant_id)
            assert len(rows) == result.total_windows
            assert all(r["model_name"]=="gpt-4.1" for r in rows)
            assert all(r["actual_model_name"]=="gpt-4.1" for r in rows)
            assert all(r["actual_provider"]=="openai" for r in rows)
            assert all(r["spent_usd"]==Decimal("0.020000") for r in rows)
        finally:
            await conn.close()
    finally:
        await engine.dispose()


async def test_n4_direct_openai_billable_partial_retains_actual_provider():
    from src.core.ai.llm_client import LLMPartialGenerationError

    class OpenAIPrimaryPartial(StubProvider):
        model_name = "gpt-4.1"
        provider_name = "openai"

        async def generate(self, *, window, tenant_id, request_id):
            self.calls.append(window.ordinal)
            raise LLMPartialGenerationError(
                "output incomplete, already billed",
                model="gpt-4.1",input_tokens=114,output_tokens=7,
                cost_usd=0.000284,
            )
    a, project, engine = await _prepare()
    runner=_runner(engine,OpenAIPrimaryPartial())
    try:
        result=await runner.run(
            authority=a,project_id=project,
            model_safe_text=_source(),n2_projection_attested=True,
        )
        assert result.stopped_reason=="PROVIDER_RESULT_UNCERTAIN"
        assert result.persisted_result_windows==0
        conn=await asyncpg.connect(_DSN)
        try:
            await conn.execute("SELECT set_config('app.current_tenant',$1,false)",str(a.tenant_id))
            row=await conn.fetchrow("""
                SELECT status,spent_usd,actual_model_name,actual_provider,
                       input_tokens,output_tokens
                FROM public.n4_usage_reservations WHERE tenant_id=$1
            """,a.tenant_id)
            assert row["status"]=="SETTLED"
            assert row["actual_model_name"]=="gpt-4.1"
            assert row["actual_provider"]=="openai"
            assert row["input_tokens"]==114
            assert row["output_tokens"]==7
            assert row["spent_usd"]==Decimal("0.000284")
        finally:
            await conn.close()
    finally:
        await engine.dispose()
