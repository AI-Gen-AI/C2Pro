"""P0 — partial billed N4 failures must not replay or lose tenant charges."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.core.ai.llm_client import LLMPartialGenerationError
from src.core.ai.tools.metadata import RetryPolicy, ToolStatus


def _billed_error() -> LLMPartialGenerationError:
    return LLMPartialGenerationError(
        "LLM continuation failed after billable response",
        model="claude-sonnet-4-6",
        input_tokens=1200,
        output_tokens=3200,
        cost_usd=0.0516,
    )


def _tool(error: LLMPartialGenerationError) -> tuple[RiskExtractionTool, AsyncMock]:
    wrapper = SimpleNamespace(generate=AsyncMock(side_effect=error))
    tool = RiskExtractionTool(anthropic_wrapper=wrapper, prompt_manager=object())
    tool.retry_policy = RetryPolicy(
        max_retries=3,
        retry_on_validation_error=True,
        exponential_backoff=True,
        initial_delay_ms=1,
    )
    return tool, wrapper.generate


@pytest.mark.asyncio
async def test_base_tool_raises_same_partial_error_without_retry() -> None:
    original = _billed_error()
    tool, generate = _tool(original)
    with pytest.raises(LLMPartialGenerationError) as caught:
        await tool._execute_with_retry(
            RiskExtractionInput(document_text="all EPC clauses"),
            tenant_id=uuid4(),
            low_budget_mode=False,
            execution_id="p0-no-replay",
        )
    assert caught.value is original
    assert generate.await_count == 1
    assert generate.await_args.args[0].use_cache is False
    assert generate.await_args.args[0].metadata["full_source_analysis"] is True


@pytest.mark.asyncio
async def test_n4_public_failure_preserves_usage_without_promoting_json(monkeypatch) -> None:
    original = _billed_error()
    tool, generate = _tool(original)
    service = MagicMock()
    service.track_usage = AsyncMock()

    @asynccontextmanager
    async def session_for(_tenant_id):
        yield object()

    monkeypatch.setattr("src.core.database.get_session_with_tenant", session_for)
    monkeypatch.setattr("src.core.ai.cost_controller.CostControllerService", lambda _db: service)
    tenant = uuid4()
    result = await tool.execute(RiskExtractionInput(document_text="contract"), tenant_id=tenant)
    assert result.status is ToolStatus.FAILED
    assert not result.success and result.data is None
    assert result.error_type == "LLMPartialGenerationError"
    assert result.model_used == original.model
    assert result.input_tokens == original.input_tokens
    assert result.output_tokens == original.output_tokens
    assert result.cost_usd == original.cost_usd
    assert "continuation failed" in result.error
    assert generate.await_count == 1
    service.track_usage.assert_awaited_once_with(tenant, original.cost_usd)
    state = {"extracted_risks": [{"title": "stale finding"}], "confidence_score": 0.98}
    updated = tool.inject_output_into_state(state, result)
    assert updated["extracted_risks"] == []
    assert updated["confidence_score"] == 0.0
    assert "continuation failed" in updated["critique_notes"]


@pytest.mark.asyncio
async def test_n4_partial_failure_with_real_isolated_postgres_tenant_ledger(
    db: AsyncSession,
    test_tenant,
    test_tenant_2,
    monkeypatch,
) -> None:
    """Real SQL UPDATE/COMMIT via existing CostControllerService, two tenants."""
    original = _billed_error()
    tool, generate = _tool(original)
    from sqlalchemy import select

    from src.core.auth.models import Tenant

    tenant_a = test_tenant.id
    tenant_b = test_tenant_2.id
    before_a = float(test_tenant.ai_spend_current)
    before_b = float(test_tenant_2.ai_spend_current)

    @asynccontextmanager
    async def isolated_tenant_session(requested_tenant):
        assert requested_tenant == tenant_a
        yield db

    monkeypatch.setattr("src.core.database.get_session_with_tenant", isolated_tenant_session)
    result = await tool.execute(
        RiskExtractionInput(document_text="EPC contract"),
        tenant_id=tenant_a,
    )
    assert result.status is ToolStatus.FAILED
    assert generate.await_count == 1
    db.expire_all()
    current_a = (await db.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    current_b = (await db.execute(select(Tenant).where(Tenant.id == tenant_b))).scalar_one()
    assert current_a.ai_spend_current == pytest.approx(before_a + original.cost_usd)
    assert current_b.ai_spend_current == pytest.approx(before_b)


@pytest.mark.asyncio
async def test_n4_ledger_write_failure_keeps_incomplete_status(monkeypatch) -> None:
    error = _billed_error()
    tool, generate = _tool(error)
    service = MagicMock()
    service.track_usage = AsyncMock(side_effect=RuntimeError("database unavailable"))

    @asynccontextmanager
    async def isolated_session(_tenant_id):
        yield object()

    monkeypatch.setattr("src.core.database.get_session_with_tenant", isolated_session)
    monkeypatch.setattr("src.core.ai.cost_controller.CostControllerService", lambda _db: service)
    result = await tool.execute(RiskExtractionInput(document_text="contract"), tenant_id=uuid4())
    assert not result.success
    assert result.status is ToolStatus.FAILED
    assert result.error_type == "LLMPartialGenerationError"
    assert result.cost_usd == error.cost_usd
    assert generate.await_count == 1
    service.track_usage.assert_awaited_once()
