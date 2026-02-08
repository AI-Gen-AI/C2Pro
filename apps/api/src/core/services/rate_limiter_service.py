"""
Rate limiter service.

Refers to Suite ID: TS-UA-SVC-RTL-001.
"""

from __future__ import annotations

from typing import Protocol

from src.core.exceptions import RateLimitExceededError


class _RedisClient(Protocol):
    def incr(self, key: str) -> int: ...
    def expire(self, key: str, seconds: int) -> bool: ...


class RateLimiterService:
    """Refers to Suite ID: TS-UA-SVC-RTL-001."""

    def __init__(self, *, redis_client: _RedisClient, limit_per_minute: int = 60) -> None:
        self.redis_client = redis_client
        self.limit_per_minute = limit_per_minute

    def check_and_increment(self, *, key: str) -> int:
        count = self.redis_client.incr(key)
        if count == 1:
            self.redis_client.expire(key, 60)
        if count > self.limit_per_minute:
            raise RateLimitExceededError(retry_after=60)
        return count
