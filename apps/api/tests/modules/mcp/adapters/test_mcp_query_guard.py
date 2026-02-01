
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any, List, Dict

# This import will fail as the modules do not exist yet.
from apps.api.src.mcp.adapters.mcp_query_guard import (
    MCPQueryGuard,
    QueryGuardConfig,
    QueryResult,
    MCPQueryExecutor,
    AuditService,
)

# --- Fixtures ---
@pytest.fixture
def mock_query_executor():
    """Mock MCPQueryExecutor with an async execute_query method."""
    mock = AsyncMock(spec=MCPQueryExecutor)
    return mock

@pytest.fixture
def mock_audit_service():
    """Mock AuditService for logging."""
    mock = AsyncMock(spec=AuditService)
    return mock

@pytest.fixture
def default_query_guard_config():
    """Default QueryGuardConfig for testing."""
    return QueryGuardConfig(max_execution_time_seconds=5, max_rows_returned=1000)

@pytest.fixture
def mcp_query_guard(mock_query_executor, mock_audit_service):
    """Fixture for MCPQueryGuard."""
    return MCPQueryGuard(
        query_executor=mock_query_executor,
        audit_service=mock_audit_service
    )

# --- Test Cases ---
@pytest.mark.asyncio
class TestMCPQueryGuard:
    """Refers to Suite ID: TS-UC-SEC-MCP-003"""

    DEFAULT_TENANT_ID = "tenant_test_id"
    SAMPLE_QUERY = "SELECT * FROM important_data"

    async def test_001_query_under_5s_allowed(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that a query completing under the timeout is allowed."""
        mock_query_executor.execute_query.return_value = ["row1", "row2"]
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result.timed_out
        assert not result.truncated
        assert result.data == ["row1", "row2"]
        mock_query_executor.execute_query.assert_called_once_with(self.SAMPLE_QUERY)

    async def test_002_query_at_5s_allowed(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that a query completing exactly at the timeout is allowed."""
        async def slow_query():
            await asyncio.sleep(default_query_guard_config.max_execution_time_seconds)
            return ["row1"]
        mock_query_executor.execute_query.return_value = await slow_query()
        
        # We need to measure if it truly takes 5s and is allowed.
        # The guard's internal timeout mechanism should handle this.
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result.timed_out
        assert not result.truncated
        assert result.data == ["row1"]

    async def test_003_query_over_5s_timeout_cancelled(self, mcp_query_guard, mock_query_executor, mock_audit_service, default_query_guard_config):
        """Test that a query exceeding the timeout is cancelled and logs an audit event."""
        async def very_slow_query():
            await asyncio.sleep(default_query_guard_config.max_execution_time_seconds + 1)
            return ["row1"] # This should not be returned if cancelled
        mock_query_executor.execute_query.return_value = await very_slow_query()
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out
        assert not result.truncated
        assert result.data == [] # No data or partial data should be returned on full timeout
        mock_audit_service.log_query_timeout.assert_called_once_with(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config.max_execution_time_seconds
        )

    async def test_004_query_result_under_1000_rows_allowed(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that a query returning fewer than max_rows_returned is allowed."""
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(500)]
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result.timed_out
        assert not result.truncated
        assert len(result.data) == 500

    async def test_005_query_result_at_1000_rows_allowed(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that a query returning exactly max_rows_returned is allowed."""
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1000)]
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result.timed_out
        assert not result.truncated
        assert len(result.data) == 1000

    async def test_006_query_result_over_1000_rows_truncated(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that a query returning more than max_rows_returned is truncated."""
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1500)]
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result.timed_out
        assert result.truncated
        assert len(result.data) == 1000
        assert result.data == [f"row{i}" for i in range(1000)] # Ensure it's the first 1000 rows

    async def test_007_query_result_truncated_flag_set(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that the truncated flag is correctly set when truncation occurs."""
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(1001)]
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.truncated
        
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(500)]
        result_no_trunc = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result_no_trunc.truncated

    async def test_008_timeout_returns_partial_results(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test that partial results are returned if a query times out after yielding some data."""
        async def partial_results_then_timeout():
            yield "partial_row_1"
            await asyncio.sleep(default_query_guard_config.max_execution_time_seconds + 1)
            yield "partial_row_2" # This should not be yielded
        
        # Mocking execute_query to return an async generator
        mock_query_executor.execute_query.return_value = partial_results_then_timeout()
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out
        assert not result.truncated
        assert result.data == ["partial_row_1"]
        mock_query_executor.execute_query.assert_called_once_with(self.SAMPLE_QUERY)


    async def test_009_timeout_audit_log_created(self, mcp_query_guard, mock_query_executor, mock_audit_service, default_query_guard_config):
        """Test that an audit log is created when a query times out."""
        async def timed_out_query():
            await asyncio.sleep(default_query_guard_config.max_execution_time_seconds + 1)
            return []
        mock_query_executor.execute_query.return_value = await timed_out_query()
        
        await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        mock_audit_service.log_query_timeout.assert_called_once_with(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config.max_execution_time_seconds
        )

    async def test_010_row_limit_audit_log_created(self, mcp_query_guard, mock_query_executor, mock_audit_service, default_query_guard_config):
        """Test that an audit log is created when the row limit is exceeded."""
        mock_query_executor.execute_query.return_value = [f"row{i}" for i in range(default_query_guard_config.max_rows_returned + 1)]
        
        await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        mock_audit_service.log_query_row_limit.assert_called_once_with(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config.max_rows_returned
        )

    async def test_011_combined_timeout_and_row_limit(self, mcp_query_guard, mock_query_executor, mock_audit_service):
        """Test a query that would both timeout and exceed row limit."""
        # Config: shorter timeout, smaller row limit
        combined_config = QueryGuardConfig(max_execution_time_seconds=1, max_rows_returned=5)

        async def very_slow_and_many_rows_query():
            for i in range(10): # Yield 10 rows
                yield f"row_long_{i}"
                await asyncio.sleep(0.5) # Each row takes 0.5s to yield
            
        # Mocking execute_query to return an async generator
        mock_query_executor.execute_query.return_value = very_slow_and_many_rows_query()
        
        # Expected behavior: It should yield some rows, then timeout
        # After 1 second (timeout), it should have yielded 2 rows (at t=0.5, t=1.0)
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, combined_config
        )
        assert result.timed_out
        assert not result.truncated # It timed out before reaching row limit, so not truncated by row count
        assert len(result.data) <= 2 # Depending on precise timing, could be 1 or 2 rows
        mock_audit_service.log_query_timeout.assert_called_once()
        mock_audit_service.log_query_row_limit.assert_not_called()

    async def test_012_query_limit_config_per_tenant(self, mcp_query_guard, mock_query_executor, mock_audit_service):
        """Test that query limits are applied based on tenant-specific configuration."""
        tenant_a_config = QueryGuardConfig(max_execution_time_seconds=2, max_rows_returned=100)
        tenant_b_config = QueryGuardConfig(max_execution_time_seconds=10, max_rows_returned=5000)

        # Tenant A: short timeout, query takes longer -> should timeout
        async def tenant_a_slow_query():
            await asyncio.sleep(3)
            return ["row"]
        mock_query_executor.execute_query.return_value = await tenant_a_slow_query()
        
        result_a = await mcp_query_guard.execute_query("tenant_a", self.SAMPLE_QUERY, tenant_a_config)
        assert result_a.timed_out
        mock_audit_service.log_query_timeout.assert_called_once()
        mock_audit_service.log_query_timeout.reset_mock() # Reset for next assertion

        # Tenant B: long timeout, query completes quickly -> should be allowed
        mock_query_executor.execute_query.return_value = ["row"] * 1000 # Under tenant B's row limit
        
        result_b = await mcp_query_guard.execute_query("tenant_b", self.SAMPLE_QUERY, tenant_b_config)
        assert not result_b.timed_out
        assert not result_b.truncated
        assert len(result_b.data) == 1000
        mock_audit_service.log_query_timeout.assert_not_called()


    async def test_edge_002_empty_result_set(self, mcp_query_guard, mock_query_executor, default_query_guard_config):
        """Test an empty result set is handled correctly."""
        mock_query_executor.execute_query.return_value = []
        
        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert not result.timed_out
        assert not result.truncated
        assert result.data == []

    async def test_edge_003_streaming_query_timeout(self, mcp_query_guard, mock_query_executor, mock_audit_service, default_query_guard_config):
        """Test a streaming query that times out after some initial data."""
        async def streaming_query_with_timeout():
            yield "stream_row_1"
            await asyncio.sleep(default_query_guard_config.max_execution_time_seconds / 2)
            yield "stream_row_2"
            await asyncio.sleep(default_query_guard_config.max_execution_time_seconds) # This sleep should trigger timeout
            yield "stream_row_3" # This should not be returned
            
        mock_query_executor.execute_query.return_value = streaming_query_with_timeout()

        result = await mcp_query_guard.execute_query(
            self.DEFAULT_TENANT_ID, self.SAMPLE_QUERY, default_query_guard_config
        )
        assert result.timed_out
        assert not result.truncated
        assert len(result.data) >= 2 # Should collect at least stream_row_1 and stream_row_2
        mock_audit_service.log_query_timeout.assert_called_once()
