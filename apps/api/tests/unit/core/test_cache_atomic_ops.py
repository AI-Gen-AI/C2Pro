"""Atomic cache primitive tests for ADR-017 governance.

TS-UT-ADR017-GOV-002
"""

from __future__ import annotations

import pytest

from src.core.cache import InMemoryCache


@pytest.mark.asyncio
async def test_in_memory_cache_incr_sets_ttl_and_decr_floors_at_zero() -> None:
    cache = InMemoryCache()

    assert await cache.incr("slots", ttl_seconds=60) == 1
    assert await cache.incr("slots", ttl_seconds=60) == 2
    assert await cache.decr("slots") == 1
    assert await cache.decr("slots") == 0
    assert await cache.decr("slots") == 0
    assert await cache.exists("slots") is False


@pytest.mark.asyncio
async def test_in_memory_cache_set_if_absent_is_single_winner() -> None:
    cache = InMemoryCache()

    assert await cache.set_if_absent("pending", "1", ttl_seconds=60) is True
    assert await cache.set_if_absent("pending", "2", ttl_seconds=60) is False
    assert await cache.get("pending") == b"1"
