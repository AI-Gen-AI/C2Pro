"""TS-AI-020: Integration coverage for route-level analytics caching."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.ai.analytics_router import get_analytics_service, router
from src.core.cache import CacheService
from src.core.security import get_current_tenant_id


class _RecordingCache(CacheService):
    def __init__(self) -> None:
        super().__init__(redis_url=None, namespace_prefix="test")
        self.set_calls: list[tuple[str, int | None]] = []

    async def set(self, key: str, value: object, ttl: int | None = None, namespace: str | None = None) -> bool:
        self.set_calls.append((key, ttl))
        return await super().set(key, value, ttl=ttl, namespace=namespace)


class _CountingAnalyticsService:
    def __init__(self) -> None:
        self.cost_calls = 0

    async def cost_breakdown(self, *, tenant_id, timeframe: str) -> dict[str, object]:
        self.cost_calls += 1
        return {
            "tenant_id": str(tenant_id),
            "timeframe": timeframe,
            "series": [],
            "summary": {"total_cost": 0, "total_tokens": 0, "total_requests": self.cost_calls},
        }


@pytest.mark.asyncio
async def test_cost_analytics_returns_cached_payload_on_second_identical_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-AI-020: Second identical tenant/query call is served from the Redis cache abstraction."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    tenant_id = str(uuid4())
    service = _CountingAnalyticsService()
    cache = _RecordingCache()
    cache_hits: list[str] = []
    cache_misses: list[str] = []

    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_analytics_service] = lambda: service
    monkeypatch.setattr("src.core.cache.get_cache_service", lambda: cache)
    monkeypatch.setattr("src.core.cache.record_cache_hit", cache_hits.append)
    monkeypatch.setattr("src.core.cache.record_cache_miss", cache_misses.append)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/api/v1/ai/analytics/cost?timeframe=7d")
        second = await client.get("/api/v1/ai/analytics/cost?timeframe=7d")

    assert first.status_code == 200
    assert second.status_code == 200
    assert service.cost_calls == 1
    assert second.json() == first.json()
    assert cache.set_calls
    assert cache.set_calls[0][1] == 300
    assert cache_misses == ["ai_analytics:cost"]
    assert cache_hits == ["ai_analytics:cost"]
