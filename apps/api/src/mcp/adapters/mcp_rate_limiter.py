
import abc
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, NamedTuple, Set

from pydantic import BaseModel, Field

# DTOs and Ports
class RateLimitConfig(BaseModel):
    """Configuration for the MCP Rate Limiter."""
    max_requests: int = Field(..., gt=0, description="Maximum number of requests allowed within the window.")
    window_seconds: int = Field(..., gt=0, description="Time window in seconds during which requests are counted.")
    warning_threshold: float = Field(0.8, gt=0, lt=1, description="Threshold (as a percentage) to issue a warning before hitting the limit.")
    midnight_reset_enabled: bool = Field(False, description="If true, resets the rate limit counter daily at midnight UTC.")

class RateLimitResult(NamedTuple):
    """Result of an allow_request call."""
    allowed: bool
    retry_after: int  # Seconds until next request might be allowed
    warning: bool     # True if usage is approaching the limit

class AuditService(abc.ABC):
    """
    Port for auditing rate limit actions.
    This defines the contract for audit logging.
    """
    @abc.abstractmethod
    async def log_rate_limit_block(self, tenant_id: str, max_requests: int, window_seconds: int) -> None:
        """
        Logs that a request for a tenant was blocked due to rate limiting.
        
        Args:
            tenant_id: The ID of the tenant whose request was blocked.
            max_requests: The maximum requests configured for the tenant.
            window_seconds: The window duration configured for the tenant.
        """
        raise NotImplementedError

# Implementation
class MCPRateLimiter:
    """
    Implements rate limiting logic for the MCP Gateway based on a sliding window.
    Supports per-tenant limits, warnings, and optional daily midnight resets.
    """
    
    def __init__(self, config: RateLimitConfig, audit_service: AuditService):
        self.config = config
        self.audit_service = audit_service
        # In-memory store: {tenant_id: [timestamp1, timestamp2, ...]}
        self._requests: Dict[str, List[float]] = {}
        # Stores the last midnight UTC for daily reset tracking: {tenant_id: datetime_object}
        self._last_midnight_reset: Dict[str, datetime] = {}

    async def allow_request(self, tenant_id: str) -> RateLimitResult:
        """
        Determines if a request from the given tenant should be allowed.

        Args:
            tenant_id: The ID of the tenant making the request.

        Returns:
            A RateLimitResult indicating if the request is allowed,
            how long to wait if not, and if a warning should be issued.
        """
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty or None")

        current_time = time.time()
        current_datetime_utc = datetime.now(timezone.utc)

        # Initialize tenant's request list if it doesn't exist
        if tenant_id not in self._requests:
            self._requests[tenant_id] = []
            self._last_midnight_reset[tenant_id] = self._get_midnight_utc(current_datetime_utc)

        # Apply midnight reset if enabled and a new day has started
        if self.config.midnight_reset_enabled:
            current_midnight = self._get_midnight_utc(current_datetime_utc)
            if self._last_midnight_reset[tenant_id] < current_midnight:
                self._requests[tenant_id] = []
                self._last_midnight_reset[tenant_id] = current_midnight
        
        # Clean up old requests outside the sliding window
        # Requests are sorted by timestamp, so we can efficiently remove from the left
        window_start_time = current_time - self.config.window_seconds
        while self._requests[tenant_id] and self._requests[tenant_id][0] < window_start_time:
            self._requests[tenant_id].pop(0)

        current_requests_in_window = len(self._requests[tenant_id])

        # Check for warning threshold
        warning = False
        if current_requests_in_window >= int(self.config.max_requests * self.config.warning_threshold):
            warning = True

        # Check if allowed
        if current_requests_in_window < self.config.max_requests:
            self._requests[tenant_id].append(current_time)
            return RateLimitResult(allowed=True, retry_after=0, warning=warning)
        else:
            # Blocked: Calculate retry_after
            # Find the timestamp of the oldest request in the window (which caused the overflow)
            # and calculate how much time is left until it expires.
            oldest_request_timestamp = self._requests[tenant_id][0] if self._requests[tenant_id] else current_time
            time_until_reset = int((oldest_request_timestamp + self.config.window_seconds) - current_time)
            if time_until_reset < 0: # Should not happen with proper sliding window, but as a safeguard
                time_until_reset = 1 # Minimum 1 second retry

            await self.audit_service.log_rate_limit_block(
                tenant_id,
                self.config.max_requests,
                self.config.window_seconds
            )
            return RateLimitResult(allowed=False, retry_after=time_until_reset, warning=False)

    def _get_midnight_utc(self, dt: datetime) -> datetime:
        """Helper to get midnight UTC for the given datetime."""
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
