"""
TS-UC-SEC-MCP-002: MCP Gateway Rate Limiting tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.mcp.adapters.mcp_rate_limiter import AuditService, MCPRateLimiter, RateLimitConfig


class _Clock:
    def __init__(self, start_epoch: float = 1_700_000_000.0) -> None:
        self.epoch = start_epoch

    def time(self) -> float:
        return self.epoch

    def now_utc(self) -> datetime:
        return datetime.fromtimestamp(self.epoch, tz=timezone.utc)

    def advance(self, seconds: float) -> None:
        self.epoch += seconds


@pytest.fixture
def rate_limit_config() -> RateLimitConfig:
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""
    return RateLimitConfig(
        max_requests=60,
        window_seconds=60,
        warning_threshold=0.8,
        midnight_reset_enabled=False,
    )


@pytest.fixture
def audit_service() -> AsyncMock:
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""
    return AsyncMock(spec=AuditService)


@pytest.fixture
def clock() -> _Clock:
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""
    return _Clock()


@pytest.fixture
def limiter(rate_limit_config: RateLimitConfig, audit_service: AsyncMock, clock: _Clock) -> MCPRateLimiter:
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""
    return MCPRateLimiter(
        config=rate_limit_config,
        audit_service=audit_service,
        time_provider=clock.time,
        datetime_provider=clock.now_utc,
    )


@pytest.mark.asyncio
class TestMCPGatewayRateLimiting:
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""

    async def test_001_request_under_limit_allowed(self, limiter: MCPRateLimiter) -> None:
        result = await limiter.allow_request("tenant_a")
        assert result.allowed is True
        assert result.retry_after == 0
        assert result.warning is False

    async def test_002_request_at_limit_59_allowed(self, limiter: MCPRateLimiter) -> None:
        for _ in range(59):
            result = await limiter.allow_request("tenant_a")
            assert result.allowed is True

    async def test_003_request_at_limit_60_allowed(self, limiter: MCPRateLimiter) -> None:
        for _ in range(60):
            result = await limiter.allow_request("tenant_a")
        assert result.allowed is True

    async def test_004_request_over_limit_61_blocked(
        self, limiter: MCPRateLimiter, audit_service: AsyncMock
    ) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        result = await limiter.allow_request("tenant_a")
        assert result.allowed is False
        assert result.retry_after > 0
        audit_service.log_rate_limit_block.assert_awaited_once_with("tenant_a", 60, 60)

    async def test_005_request_over_limit_100_blocked(self, limiter: MCPRateLimiter) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        blocked_count = 0
        for _ in range(40):
            if not (await limiter.allow_request("tenant_a")).allowed:
                blocked_count += 1
        assert blocked_count == 40

    async def test_006_window_reset_after_60_seconds(
        self, limiter: MCPRateLimiter, clock: _Clock
    ) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        assert (await limiter.allow_request("tenant_a")).allowed is False
        clock.advance(61)
        assert (await limiter.allow_request("tenant_a")).allowed is True

    async def test_007_tenant_isolation_separate_counters(self, limiter: MCPRateLimiter) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        assert (await limiter.allow_request("tenant_a")).allowed is False
        assert (await limiter.allow_request("tenant_b")).allowed is True

    async def test_008_tenant_a_full_tenant_b_available(self, limiter: MCPRateLimiter) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        assert (await limiter.allow_request("tenant_a")).allowed is False
        for _ in range(30):
            assert (await limiter.allow_request("tenant_b")).allowed is True
        assert (await limiter.allow_request("tenant_b")).allowed is True

    async def test_009_sliding_window_calculation(self, limiter: MCPRateLimiter, clock: _Clock) -> None:
        for _ in range(30):
            assert (await limiter.allow_request("tenant_a")).allowed is True
        clock.advance(30)
        for _ in range(30):
            assert (await limiter.allow_request("tenant_a")).allowed is True
        assert (await limiter.allow_request("tenant_a")).allowed is False
        clock.advance(31)
        assert (await limiter.allow_request("tenant_a")).allowed is True

    async def test_010_rate_limit_result_retry_after_header(self, limiter: MCPRateLimiter) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        result = await limiter.allow_request("tenant_a")
        assert result.allowed is False
        assert 0 < result.retry_after <= 60

    async def test_011_rate_limit_audit_log_on_block(
        self, limiter: MCPRateLimiter, audit_service: AsyncMock
    ) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        await limiter.allow_request("tenant_a")
        audit_service.log_rate_limit_block.assert_awaited_once_with("tenant_a", 60, 60)

    async def test_012_rate_limit_warning_at_80_percent(self, limiter: MCPRateLimiter) -> None:
        warning_at = int(60 * 0.8)
        for index in range(1, 61):
            result = await limiter.allow_request("tenant_a")
            if index >= warning_at:
                assert result.warning is True
            else:
                assert result.warning is False

    async def test_013_concurrent_requests_race_condition(self, limiter: MCPRateLimiter) -> None:
        results = await asyncio.gather(*[limiter.allow_request("tenant_a") for _ in range(60)])
        assert all(result.allowed for result in results)
        assert (await limiter.allow_request("tenant_a")).allowed is False

    async def test_014_rate_limit_reset_at_midnight(
        self, rate_limit_config: RateLimitConfig, audit_service: AsyncMock, clock: _Clock
    ) -> None:
        rate_limit_config.midnight_reset_enabled = True
        midnight_limiter = MCPRateLimiter(
            config=rate_limit_config,
            audit_service=audit_service,
            time_provider=clock.time,
            datetime_provider=clock.now_utc,
        )
        clock.epoch = datetime(2026, 2, 1, 23, 59, 50, tzinfo=timezone.utc).timestamp()
        for _ in range(60):
            await midnight_limiter.allow_request("tenant_a")
        assert (await midnight_limiter.allow_request("tenant_a")).allowed is False
        clock.epoch = datetime(2026, 2, 2, 0, 0, 10, tzinfo=timezone.utc).timestamp()
        assert (await midnight_limiter.allow_request("tenant_a")).allowed is True

    async def test_edge_001_burst_59_requests_simultaneous(self, limiter: MCPRateLimiter) -> None:
        results = await asyncio.gather(*[limiter.allow_request("tenant_a") for _ in range(59)])
        assert all(result.allowed for result in results)

    async def test_edge_002_exactly_60_second_boundary(
        self, limiter: MCPRateLimiter, clock: _Clock
    ) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        assert (await limiter.allow_request("tenant_a")).allowed is False
        clock.advance(60)
        assert (await limiter.allow_request("tenant_a")).allowed is True

    async def test_edge_003_empty_tenant_id_raises(self, limiter: MCPRateLimiter) -> None:
        with pytest.raises(ValueError, match="Tenant ID cannot be empty or None"):
            await limiter.allow_request("")

    async def test_edge_004_blocked_response_has_no_warning(self, limiter: MCPRateLimiter) -> None:
        for _ in range(60):
            await limiter.allow_request("tenant_a")
        result = await limiter.allow_request("tenant_a")
        assert result.allowed is False
        assert result.warning is False
