"""
Refers to Suite ID: TS-UAD-PER-RDS-001.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.core.cache import CacheService


@pytest.fixture
def redis_client() -> AsyncMock:
    client = AsyncMock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=1)
    return client


@pytest.fixture
def cache_service(monkeypatch, redis_client: AsyncMock) -> CacheService:
    monkeypatch.setattr("src.core.cache.redis.from_url", lambda *args, **kwargs: redis_client)
    return CacheService(redis_url="redis://test", namespace_prefix="c2pro")


@pytest.mark.asyncio
async def test_set_delegates_to_redis_with_ttl(cache_service: CacheService, redis_client: AsyncMock) -> None:
    ok = await cache_service.set("user:1", {"name": "Ana"}, ttl=60)

    assert ok is True
    redis_client.set.assert_awaited_once()
    key, value = redis_client.set.call_args.args[:2]
    assert key == "c2pro:user:1"
    assert value == b'{"name":"Ana"}'
    assert redis_client.set.call_args.kwargs["ex"] == 60


@pytest.mark.asyncio
async def test_get_reads_and_deserializes_json(cache_service: CacheService, redis_client: AsyncMock) -> None:
    redis_client.get.return_value = b'{"value":42}'
    value = await cache_service.get("metric:1")

    assert value == {"value": 42}
    redis_client.get.assert_awaited_once_with("c2pro:metric:1")


@pytest.mark.asyncio
async def test_delete_and_exists_use_redis(cache_service: CacheService, redis_client: AsyncMock) -> None:
    deleted = await cache_service.delete("session:1")
    exists = await cache_service.exists("session:1")

    assert deleted is True
    assert exists is True
    redis_client.delete.assert_awaited_once_with("c2pro:session:1")
    redis_client.exists.assert_awaited_once_with("c2pro:session:1")
