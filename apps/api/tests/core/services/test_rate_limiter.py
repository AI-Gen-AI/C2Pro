"""
Rate Limiter Service Tests (TDD - RED Phase)

Refers to Suite ID: TS-UA-SVC-RTL-001.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.services.rate_limiter_service import RateLimiterService
from src.core.exceptions import RateLimitExceededException


class TestRateLimiterService:
    """Refers to Suite ID: TS-UA-SVC-RTL-001."""

    def test_61st_call_within_minute_raises(self):
        redis_client = MagicMock()
        redis_client.incr.return_value = 61
        redis_client.expire.return_value = True

        service = RateLimiterService(redis_client=redis_client, limit_per_minute=60)

        with pytest.raises(RateLimitExceededException):
            service.check_and_increment(key="tenant:123")
