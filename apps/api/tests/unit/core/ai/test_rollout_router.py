"""TS-AI-LANGSMITH-032: Unit tests for deterministic rollout routing and fail-open fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.ai.rollout_router import (
    LangSmithCanaryRouter,
    LangSmithRolloutConfig,
    should_trace_request,
)


class TestLangSmithRolloutConfig:
    """Unit tests for LangSmithRolloutConfig.from_env parsing."""

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LANGSMITH_ROLLOUT_PERCENTAGE", raising=False)
        monkeypatch.delenv("LANGSMITH_ROLLOUT_FAIL_OPEN", raising=False)

        config = LangSmithRolloutConfig.from_env()

        assert config.rollout_percentage == 0
        assert config.fail_open_enabled is True

    def test_from_env_valid_percentage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LANGSMITH_ROLLOUT_PERCENTAGE", "42")
        monkeypatch.setenv("LANGSMITH_ROLLOUT_FAIL_OPEN", "true")

        config = LangSmithRolloutConfig.from_env()

        assert config.rollout_percentage == 42
        assert config.fail_open_enabled is True

    def test_from_env_invalid_percentage_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LANGSMITH_ROLLOUT_PERCENTAGE", "not-a-number")

        with pytest.raises(ValueError, match="LANGSMITH_ROLLOUT_PERCENTAGE must be an integer"):
            LangSmithRolloutConfig.from_env()

    @pytest.mark.parametrize("bad_value", ["-1", "101", "999"])
    def test_from_env_percentage_out_of_range(self, monkeypatch: pytest.MonkeyPatch, bad_value: str) -> None:
        monkeypatch.setenv("LANGSMITH_ROLLOUT_PERCENTAGE", bad_value)

        with pytest.raises(ValueError, match="LANGSMITH_ROLLOUT_PERCENTAGE must be between 0 and 100"):
            LangSmithRolloutConfig.from_env()


class TestShouldTraceRequest:
    """Unit tests for the should_trace_request function."""

    def test_zero_percent_always_false(self) -> None:
        tenant_id = uuid4()
        assert should_trace_request(tenant_id, 0) is False

    def test_100_percent_always_true(self) -> None:
        tenant_id = uuid4()
        assert should_trace_request(tenant_id, 100) is True

    def test_deterministic_for_same_tenant(self) -> None:
        tenant_id = uuid4()
        first = should_trace_request(tenant_id, 10)
        second = should_trace_request(tenant_id, 10)
        assert first is second


class TestLangSmithCanaryRouter:
    """Unit tests for the LangSmithCanaryRouter async route method."""

    @pytest.mark.asyncio
    async def test_route_legacy_call(self) -> None:
        router = LangSmithCanaryRouter(
            config=LangSmithRolloutConfig(rollout_percentage=0, fail_open_enabled=True)
        )
        traced_call = AsyncMock(return_value={"path": "traced"})
        legacy_call = AsyncMock(return_value={"path": "legacy"})

        result = await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

        assert result == {"path": "legacy"}
        traced_call.assert_not_awaited()
        legacy_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_traced_call_success(self) -> None:
        router = LangSmithCanaryRouter(
            config=LangSmithRolloutConfig(rollout_percentage=100, fail_open_enabled=False)
        )
        traced_call = AsyncMock(return_value={"path": "traced"})
        legacy_call = AsyncMock(return_value={"path": "legacy"})

        result = await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

        assert result == {"path": "traced"}
        traced_call.assert_awaited_once()
        legacy_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_route_traced_call_fails_open(self) -> None:
        router = LangSmithCanaryRouter(
            config=LangSmithRolloutConfig(rollout_percentage=100, fail_open_enabled=True)
        )
        traced_call = AsyncMock(side_effect=RuntimeError("langsmith offline"))
        legacy_call = AsyncMock(return_value={"path": "legacy"})

        result = await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

        assert result == {"path": "legacy"}
        traced_call.assert_awaited_once()
        legacy_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_traced_call_fails_closed(self) -> None:
        router = LangSmithCanaryRouter(
            config=LangSmithRolloutConfig(rollout_percentage=100, fail_open_enabled=False)
        )
        traced_call = AsyncMock(side_effect=RuntimeError("langsmith offline"))
        legacy_call = AsyncMock(return_value={"path": "legacy"})

        with pytest.raises(RuntimeError, match="langsmith offline"):
            await router.route(tenant_id=uuid4(), traced_call=traced_call, legacy_call=legacy_call)

        traced_call.assert_awaited_once()
        legacy_call.assert_not_awaited()
