"""
TS-UC-SEC-MCP-002: MCP Gateway rate limiter adapter.
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Callable, NamedTuple, Protocol

from pydantic import BaseModel, Field


class RateLimitConfig(BaseModel):
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""

    max_requests: int = Field(..., gt=0)
    window_seconds: int = Field(..., gt=0)
    warning_threshold: float = Field(0.8, gt=0, lt=1)
    midnight_reset_enabled: bool = Field(False)


class RateLimitResult(NamedTuple):
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""

    allowed: bool
    retry_after: int
    warning: bool


class AuditService(Protocol):
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""

    async def log_rate_limit_block(
        self, tenant_id: str, max_requests: int, window_seconds: int
    ) -> None: ...


class MCPRateLimiter:
    """Refers to Suite ID: TS-UC-SEC-MCP-002."""

    def __init__(
        self,
        config: RateLimitConfig,
        audit_service: AuditService,
        time_provider: Callable[[], float] | None = None,
        datetime_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.audit_service = audit_service
        self._time_provider = time_provider or time.time
        self._datetime_provider = datetime_provider or (lambda: datetime.now(timezone.utc))
        self._requests: dict[str, list[float]] = {}
        self._last_midnight_reset: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def allow_request(self, tenant_id: str) -> RateLimitResult:
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty or None")

        async with self._lock:
            now_epoch = self._time_provider()
            now_utc = self._datetime_provider()

            if tenant_id not in self._requests:
                self._requests[tenant_id] = []
                self._last_midnight_reset[tenant_id] = self._get_midnight_utc(now_utc)

            if self.config.midnight_reset_enabled:
                current_midnight = self._get_midnight_utc(now_utc)
                if self._last_midnight_reset[tenant_id] < current_midnight:
                    self._requests[tenant_id] = []
                    self._last_midnight_reset[tenant_id] = current_midnight

            window_start = now_epoch - self.config.window_seconds
            tenant_requests = self._requests[tenant_id]
            while tenant_requests and tenant_requests[0] <= window_start:
                tenant_requests.pop(0)

            if len(tenant_requests) >= self.config.max_requests:
                oldest_request = tenant_requests[0] if tenant_requests else now_epoch
                retry_after = max(
                    1,
                    int(math.ceil((oldest_request + self.config.window_seconds) - now_epoch)),
                )
                await self.audit_service.log_rate_limit_block(
                    tenant_id, self.config.max_requests, self.config.window_seconds
                )
                return RateLimitResult(allowed=False, retry_after=retry_after, warning=False)

            tenant_requests.append(now_epoch)
            warning_threshold_count = int(self.config.max_requests * self.config.warning_threshold)
            warning = len(tenant_requests) >= warning_threshold_count
            return RateLimitResult(allowed=True, retry_after=0, warning=warning)

    @staticmethod
    def _get_midnight_utc(dt: datetime) -> datetime:
        return dt.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
