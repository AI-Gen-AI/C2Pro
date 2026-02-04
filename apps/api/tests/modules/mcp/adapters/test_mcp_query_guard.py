"""
TS-UC-SEC-MCP-003: MCP Gateway Query Limits tests.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock

import pytest

from src.mcp.adapters.mcp_query_guard import (
    AuditService,
    MCPQueryExecutor,
    MCPQueryGuard,
    QueryGuardConfig,
)


@pytest.fixture
def mock_query_executor() -> AsyncMock:
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""
    return AsyncMock(spec=MCPQueryExecutor)


@pytest.fixture
def mock_audit_service() -> AsyncMock:
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""
    return AsyncMock(spec=AuditService)


@pytest.fixture
def default_query_guard_config() -> QueryGuardConfig:
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""
    return QueryGuardConfig(max_execution_time_seconds=0.05, max_rows_returned=1000)


@pytest.fixture
def mcp_query_guard(mock_query_executor: AsyncMock, mock_audit_service: AsyncMock) -> MCPQueryGuard:
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""
    return MCPQueryGuard(query_executor=mock_query_executor, audit_service=mock_audit_service)


def _stream_rows(rows: list[Any], delay_seconds: float = 0.0) -> AsyncIterator[Any]:
    async def _gen() -> AsyncIterator[Any]:
        for row in rows:
            yield row
            if delay_seconds:
                await asyncio.sleep(delay_seconds)

    return _gen()


@pytest.mark.asyncio
class TestMCPQueryGuard:
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""

    DEFAULT_TENANT_ID = "tenant_test_id"
    SAMPLE_QUERY = "SELECT * FROM important_data"

    async def test_001_query_under_5s_allowed(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = ["row1", "row2"]
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out is False
        assert result.truncated is False
        assert result.data == ["row1", "row2"]

    async def test_002_query_at_5s_allowed(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
    ) -> None:
        config = QueryGuardConfig(max_execution_time_seconds=0.05, max_rows_returned=1000)

        async def fast_query() -> list[str]:
            await asyncio.sleep(0.01)
            return ["row1"]

        async def _exec_fast(_query: str) -> list[str]:
            return await fast_query()

        mock_query_executor.execute_query.side_effect = _exec_fast
        result = await mcp_query_guard.execute_query(self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config)
        assert result.timed_out is False
        assert result.truncated is False
        assert result.data == ["row1"]

    async def test_003_query_over_5s_timeout_cancelled(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        config = QueryGuardConfig(max_execution_time_seconds=0.02, max_rows_returned=1000)

        async def very_slow_query() -> list[str]:
            await asyncio.sleep(0.04)
            return ["row1"]

        async def _exec_slow(_query: str) -> list[str]:
            return await very_slow_query()

        mock_query_executor.execute_query.side_effect = _exec_slow
        result = await mcp_query_guard.execute_query(self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config)
        assert result.timed_out is True
        assert result.truncated is False
        assert result.data == []
        mock_audit_service.log_query_timeout.assert_awaited_once_with(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config.max_execution_time_seconds
        )

    async def test_004_query_result_under_1000_rows_allowed(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(500)]
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out is False
        assert result.truncated is False
        assert len(result.data) == 500

    async def test_005_query_result_at_1000_rows_allowed(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1000)]
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out is False
        assert result.truncated is False
        assert len(result.data) == 1000

    async def test_006_query_result_over_1000_rows_truncated(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1500)]
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out is False
        assert result.truncated is True
        assert len(result.data) == 1000

    async def test_007_query_result_truncated_flag_set(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1001)]
        assert (
            await mcp_query_guard.execute_query(
                self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
            )
        ).truncated is True

        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(500)]
        assert (
            await mcp_query_guard.execute_query(
                self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
            )
        ).truncated is False

    async def test_008_timeout_returns_partial_results(
        self, mcp_query_guard: MCPQueryGuard, mock_query_executor: AsyncMock
    ) -> None:
        config = QueryGuardConfig(max_execution_time_seconds=0.02, max_rows_returned=1000)

        async def partial_then_timeout() -> AsyncIterator[str]:
            yield "partial_row_1"
            await asyncio.sleep(0.05)
            yield "partial_row_2"

        mock_query_executor.execute_query.return_value = partial_then_timeout()
        result = await mcp_query_guard.execute_query(self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config)
        assert result.timed_out is True
        assert result.truncated is False
        assert result.data == ["partial_row_1"]

    async def test_009_timeout_audit_log_created(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        config = QueryGuardConfig(max_execution_time_seconds=0.02, max_rows_returned=1000)

        async def very_slow_query() -> list[str]:
            await asyncio.sleep(0.05)
            return ["row1"]

        async def _exec_slow(_query: str) -> list[str]:
            return await very_slow_query()

        mock_query_executor.execute_query.side_effect = _exec_slow
        await mcp_query_guard.execute_query(self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config)
        mock_audit_service.log_query_timeout.assert_awaited_once_with(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config.max_execution_time_seconds
        )

    async def test_010_row_limit_audit_log_created(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        mock_audit_service: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1001)]
        await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        mock_audit_service.log_query_row_limit.assert_awaited_once_with(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config.max_rows_returned
        )

    async def test_011_combined_timeout_and_row_limit(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        config = QueryGuardConfig(max_execution_time_seconds=0.03, max_rows_returned=5)
        mock_query_executor.execute_query.return_value = _stream_rows(
            [f"row{i}" for i in range(20)], delay_seconds=0.02
        )
        result = await mcp_query_guard.execute_query(self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config)
        assert result.timed_out is True
        assert result.truncated is False
        assert len(result.data) <= 2
        mock_audit_service.log_query_timeout.assert_awaited_once()
        mock_audit_service.log_query_row_limit.assert_not_awaited()

    async def test_012_query_limit_config_per_tenant(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        tenant_a_config = QueryGuardConfig(max_execution_time_seconds=0.01, max_rows_returned=100)
        tenant_b_config = QueryGuardConfig(max_execution_time_seconds=0.1, max_rows_returned=5000)

        async def slow_query() -> list[str]:
            await asyncio.sleep(0.03)
            return ["row"]

        async def _exec_slow(_query: str) -> list[str]:
            return await slow_query()

        mock_query_executor.execute_query.side_effect = _exec_slow
        result_a = await mcp_query_guard.execute_query("tenant_a", self.SAMPLE_QUERY, tenant_a_config)
        assert result_a.timed_out is True
        mock_audit_service.log_query_timeout.assert_awaited_once()
        mock_audit_service.log_query_timeout.reset_mock()

        mock_query_executor.execute_query.side_effect = None
        mock_query_executor.execute_query.return_value = ["row"] * 1000
        result_b = await mcp_query_guard.execute_query("tenant_b", self.SAMPLE_QUERY, tenant_b_config)
        assert result_b.timed_out is False
        assert result_b.truncated is False
        assert len(result_b.data) == 1000
        mock_audit_service.log_query_timeout.assert_not_awaited()

    async def test_edge_001_exactly_1000_rows(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1000)]
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert len(result.data) == 1000
        assert result.truncated is False

    async def test_edge_002_empty_result_set(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        default_query_guard_config: QueryGuardConfig,
    ) -> None:
        mock_query_executor.execute_query.return_value = []
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out is False
        assert result.truncated is False
        assert result.data == []

    async def test_edge_003_streaming_query_timeout(
        self,
        mcp_query_guard: MCPQueryGuard,
        mock_query_executor: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        config = QueryGuardConfig(max_execution_time_seconds=0.03, max_rows_returned=1000)
        mock_query_executor.execute_query.return_value = _stream_rows(
            ["stream_row_1", "stream_row_2", "stream_row_3"], delay_seconds=0.02
        )
        result = await mcp_query_guard.execute_query(self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, config)
        assert result.timed_out is True
        assert result.truncated is False
        assert len(result.data) >= 1
        mock_audit_service.log_query_timeout.assert_awaited_once()
