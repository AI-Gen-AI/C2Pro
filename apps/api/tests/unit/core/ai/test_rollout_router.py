"""TS-AI-LANGSMITH-032: Unit tests for deterministic rollout routing and fail-open fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.ai.rollout_router import LangSmithCanaryRouter, LangSmithRolloutConfig, should_trace_request


def test_should_trace_request_is_deterministic_for_same_tenant() -> None:
    tenant_id = uuid4()
    first = should_trace_request(tenant_id, 10)
    second = should_trace_request(tenant_id, 10)
    assert first is second


def test_should_trace_request_handles_bounds() -> None:
    tenant_id = uuid4()
    assert should_trace_request(tenant_id, 0) is False
    assert should_trace_request(tenant_id, 100) is True


@pytest.mark.asyncio
async def test_router_routes_to_legacy_when_tenant_outside_rollout() -> None:
    router = LangSmithCanaryRouter(config=LangSmithRolloutConfig(rollout_percentage=0, fail_open_enabled=True))
    traced_call = AsyncMock(return_value={"path": "traced"})
    legacy_call = AsyncMock(return_value={"path": "legacy"})

    result = await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

    assert result == {"path": "legacy"}
    traced_call.assert_not_awaited()
    legacy_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_router_falls_back_to_legacy_when_traced_call_fails() -> None:
    router = LangSmithCanaryRouter(config=LangSmithRolloutConfig(rollout_percentage=100, fail_open_enabled=True))
    traced_call = AsyncMock(side_effect=RuntimeError("langsmith offline"))
    legacy_call = AsyncMock(return_value={"path": "legacy"})

    result = await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

    assert result == {"path": "legacy"}
    traced_call.assert_awaited_once()
    legacy_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_router_raises_when_fail_open_disabled() -> None:
    router = LangSmithCanaryRouter(config=LangSmithRolloutConfig(rollout_percentage=100, fail_open_enabled=False))
    traced_call = AsyncMock(side_effect=RuntimeError("langsmith offline"))
    legacy_call = AsyncMock(return_value={"path": "legacy"})

    with pytest.raises(RuntimeError, match="langsmith offline"):
        await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

    traced_call.assert_awaited_once()
    legacy_call.assert_not_awaited()
