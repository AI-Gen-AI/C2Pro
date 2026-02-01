
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

# This import will fail as the modules do not exist yet.
from apps.api.src.mcp.adapters.mcp_rate_limiter import (
    MCPRateLimiter,
    RateLimitConfig,
    AuditService,
    RateLimitResult,
)


# Fixtures for common mocks and objects
@pytest.fixture
def mock_rate_limit_config():
    """Mock RateLimitConfig with default values."""
    mock = MagicMock(spec=RateLimitConfig)
    mock.max_requests = 60
    mock.window_seconds = 60
    mock.warning_threshold = 0.8  # 80%
    mock.midnight_reset_enabled = False
    return mock


@pytest.fixture
def mock_audit_service():
    """Mock AuditService."""
    return MagicMock(spec=AuditService)


@pytest.fixture
def mcp_rate_limiter(mock_rate_limit_config, mock_audit_service):
    """Fixture for MCPRateLimiter."""
    return MCPRateLimiter(
        config=mock_rate_limit_config, audit_service=mock_audit_service
    )


@pytest.mark.asyncio
class TestMCPGatewayRateLimiting:
    """Refers to Suite ID: TS-UC-SEC-MCP-002"""

    DEFAULT_TENANT_ID = "tenant_test_id"
    DEFAULT_OPERATION = "test_operation"  # Rate limiting applies per tenant, not per operation in this suite

    async def test_001_request_under_limit_allowed(self, mcp_rate_limiter):
        """Test that a single request under the limit is allowed."""
        result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
        assert result.allowed is True
        assert result.retry_after == 0
        assert result.warning is False

    async def test_002_request_at_limit_59_allowed(self, mcp_rate_limiter):
        """Test that 59 requests (just under the limit) are allowed."""
        for _ in range(59):
            result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
            assert result.allowed is True
            assert result.retry_after == 0
            assert result.warning is False

    async def test_003_request_at_limit_60_allowed(self, mcp_rate_limiter):
        """Test that exactly 60 requests (at the limit) are allowed."""
        for i in range(60):
            result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
            assert result.allowed is True
            assert result.retry_after == 0
            if i == 59 * 0.8:  # Simplified check for warning at 80%
                 assert result.warning is True # The 48th request for default (60 requests limit)
            else:
                 assert result.warning is False

    async def test_004_request_over_limit_61_blocked(self, mcp_rate_limiter, mock_audit_service):
        """Test that the 61st request is blocked and audit service is called."""
        for _ in range(60):
            await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)

        result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
        assert result.allowed is False
        assert result.retry_after > 0
        assert result.warning is False
        mock_audit_service.log_rate_limit_block.assert_called_once_with(self.DEFAULT_TENANT_ID)

    async def test_005_request_over_limit_100_blocked(self, mcp_rate_limiter):
        """Test that multiple requests over the limit are blocked."""
        for _ in range(60):
            await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)

        blocked_count = 0
        for _ in range(40):  # 40 additional requests
            result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
            if not result.allowed:
                blocked_count += 1
        assert blocked_count == 40

    async def test_006_window_reset_after_60_seconds(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that the rate limit window resets after 60 seconds."""
        # Fill the window
        for _ in range(mock_rate_limit_config.max_requests):
            await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)

        # Attempt one more, should be blocked
        result_blocked = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
        assert result_blocked.allowed is False

        # Advance time past the window
        # For simplicity, we'll mock time.time() directly within the test
        with patch('time.time', return_value=time.time() + mock_rate_limit_config.window_seconds + 1):
            # Make a new request, should be allowed
            result_allowed = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
            assert result_allowed.allowed is True

    async def test_007_tenant_isolation_separate_counters(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that different tenants have separate rate limit counters."""
        tenant_a = "tenant_a"
        tenant_b = "tenant_b"

        # Tenant A fills its limit
        for _ in range(mock_rate_limit_config.max_requests):
            await mcp_rate_limiter.allow_request(tenant_a)

        # Tenant A's next request should be blocked
        result_a_blocked = await mcp_rate_limiter.allow_request(tenant_a)
        assert result_a_blocked.allowed is False

        # Tenant B should still be able to make a request
        result_b_allowed = await mcp_rate_limiter.allow_request(tenant_b)
        assert result_b_allowed.allowed is True

    async def test_008_tenant_a_full_tenant_b_available(self, mcp_rate_limiter, mock_rate_limit_config):
        """Specific scenario: Tenant A full, Tenant B still has capacity."""
        tenant_a = "tenant_a_full"
        tenant_b = "tenant_b_available"

        # Tenant A fills its limit
        for _ in range(mock_rate_limit_config.max_requests):
            await mcp_rate_limiter.allow_request(tenant_a)
        result_a_blocked = await mcp_rate_limiter.allow_request(tenant_a)
        assert result_a_blocked.allowed is False

        # Tenant B makes some requests but not all
        for _ in range(mock_rate_limit_config.max_requests // 2):
            result_b_partial = await mcp_rate_limiter.allow_request(tenant_b)
            assert result_b_partial.allowed is True

        # Tenant B should still be allowed to make more requests
        result_b_allowed_again = await mcp_rate_limiter.allow_request(tenant_b)
        assert result_b_allowed_again.allowed is True

    async def test_009_sliding_window_calculation(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that the sliding window correctly expires old requests."""
        tenant_id = "sliding_window_tenant"
        max_requests = mock_rate_limit_config.max_requests
        window_seconds = mock_rate_limit_config.window_seconds

        # Simulate requests over a period less than the window
        # 30 requests at t=0
        current_time = datetime.now()
        with patch('datetime.now', return_value=current_time):
            for _ in range(max_requests // 2):
                result = await mcp_rate_limiter.allow_request(tenant_id)
                assert result.allowed is True

        # Advance time by (window_seconds / 2) - 1 seconds
        time_mid_window = current_time + timedelta(seconds=window_seconds // 2 - 1)
        with patch('datetime.now', return_value=time_mid_window):
            # Make 30 more requests (total 60)
            for _ in range(max_requests // 2):
                result = await mcp_rate_limiter.allow_request(tenant_id)
                assert result.allowed is True
            
            # One more request should be blocked (61st in total within the current window)
            result_blocked = await mcp_rate_limiter.allow_request(tenant_id)
            assert result_blocked.allowed is False
        
        # Advance time past the start of the first 30 requests, but within the window for the second 30
        # This will remove the initial 30 requests from the window, allowing more requests.
        time_past_first_batch = current_time + timedelta(seconds=window_seconds + 1)
        with patch('datetime.now', return_value=time_past_first_batch):
            # Now, the first 30 requests should have expired, allowing another 30 requests.
            # There were 30 requests made at 'time_mid_window'.
            # So, the effective count should be 30. We can make (max_requests - 30) more.
            # In this case, 60 - 30 = 30 more requests should be allowed.
            for _ in range(max_requests // 2):
                result = await mcp_rate_limiter.allow_request(tenant_id)
                assert result.allowed is True
            
            # One more should be blocked
            result_blocked_again = await mcp_rate_limiter.allow_request(tenant_id)
            assert result_blocked_again.allowed is False


    async def test_010_rate_limit_result_retry_after_header(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that when blocked, Retry-After is correctly set."""
        # Fill the window
        for _ in range(mock_rate_limit_config.max_requests):
            await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)

        # The next request should be blocked and have retry_after > 0
        result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
        assert result.allowed is False
        assert result.retry_after > 0
        assert result.retry_after <= mock_rate_limit_config.window_seconds # Should be within the window

    async def test_011_rate_limit_audit_log_on_block(self, mcp_rate_limiter, mock_audit_service):
        """Test that the audit service logs when a request is blocked."""
        # Fill the window
        for _ in range(mcp_rate_limiter.config.max_requests):
            await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)

        # Make one more request to trigger block
        await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
        mock_audit_service.log_rate_limit_block.assert_called_once_with(self.DEFAULT_TENANT_ID, mcp_rate_limiter.config.max_requests, mcp_rate_limiter.config.window_seconds)

    async def test_012_rate_limit_warning_at_80_percent(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that a warning is issued when usage reaches 80% of the limit."""
        warning_threshold_count = int(mock_rate_limit_config.max_requests * mock_rate_limit_config.warning_threshold)
        
        # Requests up to warning threshold - 1 should not have warning
        for _ in range(warning_threshold_count - 1):
            result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
            assert result.allowed is True
            assert result.warning is False

        # The request at the warning threshold should have warning
        result_warning = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
        assert result_warning.allowed is True
        assert result_warning.warning is True

        # Requests after warning threshold but before limit should still have warning
        for _ in range(mock_rate_limit_config.max_requests - warning_threshold_count -1):
            result = await mcp_rate_limiter.allow_request(self.DEFAULT_TENANT_ID)
            assert result.allowed is True
            assert result.warning is True

    async def test_013_concurrent_requests_race_condition(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that concurrent requests handle race conditions correctly."""
        tenant_id = "concurrent_tenant"
        max_requests = mock_rate_limit_config.max_requests

        # Simulate max_requests concurrent requests
        tasks = [mcp_rate_limiter.allow_request(tenant_id) for _ in range(max_requests)]
        results = await asyncio.gather(*tasks)

        # All requests should be allowed
        for result in results:
            assert result.allowed is True
            assert result.warning is False  # For simplicity, not checking warning here

        # One more concurrent request should be blocked
        blocked_result = await mcp_rate_limiter.allow_request(tenant_id)
        assert blocked_result.allowed is False
        assert blocked_result.retry_after > 0

    async def test_014_rate_limit_reset_at_midnight(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that the rate limit resets at midnight if enabled."""
        mock_rate_limit_config.midnight_reset_enabled = True
        tenant_id = "midnight_reset_tenant"
        
        # Simulate time just before midnight
        current_dt = datetime(2026, 2, 1, 23, 59, 50, tzinfo=timezone.utc)
        with patch('datetime.now', return_value=current_dt):
            # Fill the limit
            for _ in range(mock_rate_limit_config.max_requests):
                await mcp_rate_limiter.allow_request(tenant_id)
            
            result_blocked = await mcp_rate_limiter.allow_request(tenant_id)
            assert result_blocked.allowed is False

        # Simulate time just after midnight
        next_day_dt = datetime(2026, 2, 2, 0, 0, 10, tzinfo=timezone.utc)
        with patch('datetime.now', return_value=next_day_dt):
            # New request should be allowed as limit reset
            result_allowed = await mcp_rate_limiter.allow_request(tenant_id)
            assert result_allowed.allowed is True

    async def test_edge_001_burst_59_requests_simultaneous(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test that a burst of 59 simultaneous requests are all allowed."""
        tenant_id = "burst_tenant"
        num_requests = 59
        tasks = [mcp_rate_limiter.allow_request(tenant_id) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)

        for result in results:
            assert result.allowed is True

    async def test_edge_002_exactly_60_second_boundary(self, mcp_rate_limiter, mock_rate_limit_config):
        """Test behavior at exact 60-second boundary."""
        tenant_id = "boundary_tenant"
        max_requests = mock_rate_limit_config.max_requests
        
        start_time = datetime.now()
        with patch('datetime.now', return_value=start_time):
            for _ in range(max_requests):
                await mcp_rate_limiter.allow_request(tenant_id)
            
            result_blocked_at_limit = await mcp_rate_limiter.allow_request(tenant_id)
            assert result_blocked_at_limit.allowed is False

        # Advance time by exactly 60 seconds
        exact_window_end_time = start_time + timedelta(seconds=mock_rate_limit_config.window_seconds)
        with patch('datetime.now', return_value=exact_window_end_time):
            # The requests from `start_time` should now be outside the window.
            # Another request should be allowed.
            result_allowed_after_window = await mcp_rate_limiter.allow_request(tenant_id)
            assert result_allowed_after_window.allowed is True

