"""
TS-UC-SEC-MCP-002, TS-UC-SEC-MCP-004: MCP rate limit and audit persistence tests.
"""

from __future__ import annotations

import json
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from src.core.mcp.servers.database_server import (
    DatabaseMCPServer,
    InMemoryRateLimitBackend,
    QueryLimits,
    RateLimits,
    RedisRateLimitBackend,
)


class _Clock:
    def __init__(self, start_epoch: float = 1_700_000_000.0) -> None:
        self.epoch = start_epoch

    def time(self) -> float:
        return self.epoch


@pytest.mark.asyncio
async def test_redis_rate_limit_backend_tracks_requests_per_tenant() -> None:
    redis_client = AsyncMock()
    redis_client.zcard.side_effect = [0, 1, 2]
    backend = RedisRateLimitBackend(redis_client=redis_client)
    tenant_id = str(uuid4())

    first = await backend.increment_and_get_count(tenant_id=tenant_id, now_epoch=100.0, window_seconds=60)
    second = await backend.increment_and_get_count(tenant_id=tenant_id, now_epoch=101.0, window_seconds=60)
    third = await backend.increment_and_get_count(tenant_id=tenant_id, now_epoch=102.0, window_seconds=60)

    assert (first, second, third) == (1, 2, 3)
    redis_client.zremrangebyscore.assert_any_await(f"mcp:rate-limit:{tenant_id}", "-inf", 40.0)
    redis_client.expire.assert_any_await(f"mcp:rate-limit:{tenant_id}", 300)


@pytest.mark.asyncio
async def test_log_query_persists_audit_row_to_database() -> None:
    db = AsyncMock()
    server = DatabaseMCPServer(
        query_limits=QueryLimits(statement_timeout="2s", row_limit=100, max_cost=5000),
        rate_limits=RateLimits(per_tenant_per_minute=10, per_tenant_per_hour=100),
    )
    tenant_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()

    await server._log_query(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        query_type="view",
        view_name="v_project_summary",
        function_name=None,
        project_id=project_id,
        row_count=3,
        execution_time_ms=12.5,
    )

    assert db.execute.await_count == 1
    statement = db.execute.await_args.args[0]
    params = db.execute.await_args.args[1]
    assert "INSERT INTO audit_logs" in str(statement)
    assert params["tenant_id"] == tenant_id
    assert params["user_id"] == user_id
    assert params["resource_id"] == project_id
    assert params["action"] == "mcp.query.view"
    assert params["resource_type"] == "mcp_view"
    assert json.loads(params["changes"])["view_name"] == "v_project_summary"


@pytest.mark.asyncio
async def test_rate_limit_status_uses_persistent_backend_counts() -> None:
    clock = _Clock()
    backend = InMemoryRateLimitBackend()
    server = DatabaseMCPServer(
        query_limits=QueryLimits(statement_timeout="2s", row_limit=100, max_cost=5000),
        rate_limits=RateLimits(per_tenant_per_minute=3, per_tenant_per_hour=100),
        rate_limit_backend=backend,
        time_provider=clock.time,
    )
    tenant_id = uuid4()

    await server._check_rate_limit(tenant_id)
    await server._check_rate_limit(tenant_id)

    status = await server.get_rate_limit_status(tenant_id)

    assert status["requests_in_window"] == 2
    assert status["remaining"] == 1
