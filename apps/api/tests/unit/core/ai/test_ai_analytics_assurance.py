"""C2PRO-DEV-15 Wave 3.7 assurance for live AI analytics authority."""

from __future__ import annotations

import tomllib
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.ai.analytics_router import get_analytics_service, router
from src.core.ai.analytics_service import (
    AIAnalyticsService,
    _parse_timeframe,
    _window_start,
)
from src.core.cache import CacheService
from src.core.security import get_current_tenant_id


def _result_all(rows: list[dict[str, object]]) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    return result


def _result_one(row: dict[str, object]) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.one.return_value = row
    return result


def test_ai_analytics_authorities_are_measured_by_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    pyproject = tomllib.loads(
        (repo_root / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )
    omitted = set(pyproject["tool"]["coverage"]["run"]["omit"])

    assert "src/core/ai/analytics_router.py" not in omitted
    assert "src/core/ai/analytics_service.py" not in omitted


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("12w", timedelta(weeks=12)),
        (" 7D ", timedelta(days=7)),
    ],
)
def test_parse_timeframe_accepts_positive_supported_units(
    raw: str,
    expected: timedelta,
) -> None:
    assert _parse_timeframe(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "7",
        "d",
        "-7d",
        "7m",
        "0h",
        "0d",
        "0w",
        "1000000000d",
        "1000000000w",
    ],
)
def test_parse_timeframe_rejects_invalid_or_unbounded_values(raw: str) -> None:
    with pytest.raises(ValueError, match="Invalid timeframe"):
        _parse_timeframe(raw)


def test_window_start_converts_datetime_underflow_to_validation_error() -> None:
    with pytest.raises(ValueError, match="Invalid timeframe"):
        _window_start("999999999d")


def test_service_cache_key_is_tenant_and_scope_specific() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()

    a = AIAnalyticsService._cache_key(
        tenant_id=tenant_a,
        metric="comparison",
        timeframe="30d",
        scope="a-vs-b",
    )
    b = AIAnalyticsService._cache_key(
        tenant_id=tenant_b,
        metric="comparison",
        timeframe="30d",
        scope="a-vs-b",
    )
    other_scope = AIAnalyticsService._cache_key(
        tenant_id=tenant_a,
        metric="comparison",
        timeframe="30d",
        scope="b-vs-c",
    )

    assert a != b
    assert a != other_scope
    assert str(tenant_a) in a
    assert str(tenant_b) in b


@pytest.mark.asyncio
async def test_service_cache_failures_are_soft() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(side_effect=RuntimeError("cache unavailable"))
    cache.set = AsyncMock(side_effect=RuntimeError("cache unavailable"))
    service = AIAnalyticsService(db=AsyncMock(), cache=cache)

    assert await service._get_cached("key") is None
    await service._set_cached("key", {"ok": True}, ttl_seconds=30)

    cache.get.assert_awaited_once_with("key")
    cache.set.assert_awaited_once_with("key", {"ok": True}, ttl=30)


@pytest.mark.asyncio
async def test_service_cache_helpers_noop_when_cache_disabled() -> None:
    service = AIAnalyticsService(db=AsyncMock(), cache=None)

    assert await service._get_cached("key") is None
    await service._set_cached("key", {"ok": True}, ttl_seconds=30)
    await service.invalidate_tenant_analytics(uuid4())


@pytest.mark.asyncio
async def test_invalidate_tenant_analytics_removes_supported_metric_windows() -> None:
    cache = MagicMock()
    cache.delete = AsyncMock()
    tenant_id = uuid4()
    service = AIAnalyticsService(db=AsyncMock(), cache=cache)

    await service.invalidate_tenant_analytics(tenant_id)

    assert cache.delete.await_count == 12
    deleted = {call.args[0] for call in cache.delete.await_args_list}
    assert (
        AIAnalyticsService._cache_key(
            tenant_id=tenant_id,
            metric="cost",
            timeframe="24h",
        )
        in deleted
    )
    assert (
        AIAnalyticsService._cache_key(
            tenant_id=tenant_id,
            metric="quality-drift",
            timeframe="90d",
        )
        in deleted
    )


@pytest.mark.asyncio
async def test_cost_breakdown_is_tenant_scoped_and_maps_summary() -> None:
    tenant_id = uuid4()
    bucket = _window_start("24h")
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result_all(
                [
                    {
                        "bucket": bucket,
                        "model_name": "claude-sonnet",
                        "prompt_version": "v3",
                        "request_count": 2,
                        "total_tokens": 120,
                        "total_cost": 0.08,
                        "avg_latency_ms": 240.0,
                    }
                ]
            ),
            _result_one(
                {
                    "total_cost": 0.08,
                    "total_tokens": 120,
                    "total_requests": 2,
                }
            ),
        ]
    )
    service = AIAnalyticsService(db=db, cache=None)

    payload = await service.cost_breakdown(tenant_id=tenant_id, timeframe="7d")

    assert payload["timeframe"] == "7d"
    assert payload["summary"] == {
        "total_cost": 0.08,
        "total_tokens": 120,
        "total_requests": 2,
    }
    assert payload["series"][0]["model"] == "claude-sonnet"
    assert payload["series"][0]["prompt_version"] == "v3"
    assert db.execute.await_count == 2
    for call in db.execute.await_args_list:
        assert call.args[1]["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_version_performance_maps_rates_feedback_and_tenant_scope() -> None:
    tenant_id = uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_result_all(
            [
                {
                    "prompt_version": "v2",
                    "prompt_tag": "stable",
                    "total_runs": 4,
                    "success_runs": 3,
                    "avg_latency_ms": 150.0,
                    "total_cost": 0.4,
                    "feedback_count": 2,
                    "avg_feedback_score": 0.75,
                }
            ]
        )
    )
    service = AIAnalyticsService(db=db, cache=None)

    payload = await service.version_performance(tenant_id=tenant_id, timeframe="30d")

    row = payload["versions"][0]
    assert row["success_rate"] == pytest.approx(0.75)
    assert row["feedback_count"] == 2
    assert row["avg_feedback_score"] == pytest.approx(0.75)
    assert db.execute.await_args.args[1]["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_version_performance_handles_zero_run_defensively() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_result_all(
            [
                {
                    "prompt_version": "v0",
                    "prompt_tag": "empty",
                    "total_runs": 0,
                    "success_runs": 0,
                    "avg_latency_ms": 0,
                    "total_cost": 0,
                    "feedback_count": 0,
                    "avg_feedback_score": 0,
                }
            ]
        )
    )
    service = AIAnalyticsService(db=db, cache=None)

    payload = await service.version_performance(tenant_id=uuid4(), timeframe="7d")

    assert payload["versions"][0]["success_rate"] == 0


@pytest.mark.asyncio
async def test_compare_versions_normalizes_missing_candidate_and_computes_delta() -> None:
    tenant_id = uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_result_all(
            [
                {
                    "prompt_version": "v1",
                    "total_runs": 10,
                    "success_runs": 8,
                    "avg_latency_ms": 200.0,
                    "total_cost": 1.0,
                    "avg_feedback_score": 0.7,
                }
            ]
        )
    )
    service = AIAnalyticsService(db=db, cache=None)

    payload = await service.compare_versions(
        tenant_id=tenant_id,
        timeframe="30d",
        baseline_version="v1",
        candidate_version="v2",
    )

    assert payload["baseline"]["success_rate"] == pytest.approx(0.8)
    assert payload["candidate"] == {
        "prompt_version": "v2",
        "total_runs": 0,
        "success_rate": 0.0,
        "avg_latency_ms": 0.0,
        "total_cost": 0.0,
        "avg_feedback_score": 0.0,
    }
    assert payload["delta"]["success_rate"] == pytest.approx(-0.8)
    params = db.execute.await_args.args[1]
    assert params["tenant_id"] == tenant_id
    assert params["baseline"] == "v1"
    assert params["candidate"] == "v2"


@pytest.mark.asyncio
async def test_quality_drift_emits_feedback_and_latency_alerts() -> None:
    tenant_id = uuid4()
    first = _window_start("48h")
    second = _window_start("24h")
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_result_all(
            [
                {
                    "bucket": first,
                    "operation_type": "contract_analysis",
                    "run_count": 10,
                    "avg_latency_ms": 100.0,
                    "avg_feedback_score": 0.8,
                    "feedback_count": 8,
                },
                {
                    "bucket": second,
                    "operation_type": "contract_analysis",
                    "run_count": 12,
                    "avg_latency_ms": 140.0,
                    "avg_feedback_score": 0.5,
                    "feedback_count": 9,
                },
            ]
        )
    )
    service = AIAnalyticsService(db=db, cache=None)

    payload = await service.quality_drift(tenant_id=tenant_id, timeframe="30d")

    alert_types = {alert["type"] for alert in payload["alerts"]}
    assert alert_types == {"feedback_drop", "latency_spike"}
    assert payload["series"][0]["operation"] == "contract_analysis"
    assert db.execute.await_args.args[1]["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_service_cache_hit_short_circuits_database() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(return_value={"timeframe": "7d", "versions": [{"cached": True}]})
    db = AsyncMock()
    service = AIAnalyticsService(db=db, cache=cache)

    payload = await service.version_performance(tenant_id=uuid4(), timeframe="7d")

    assert payload["versions"] == [{"cached": True}]
    db.execute.assert_not_awaited()


class _RecordingRouteCache(CacheService):
    def __init__(self) -> None:
        super().__init__(redis_url=None, namespace_prefix="dev15-analytics")
        self.set_calls: list[tuple[str, int | None]] = []

    async def set(
        self,
        key: str,
        value: object,
        ttl: int | None = None,
        namespace: str | None = None,
    ) -> bool:
        self.set_calls.append((key, ttl))
        return await super().set(key, value, ttl=ttl, namespace=namespace)


class _RouterService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, str]] = []
        self.raise_value_error = False

    def _record(self, metric: str, tenant_id: UUID, timeframe: str) -> None:
        if self.raise_value_error:
            raise ValueError("Invalid timeframe")
        self.calls.append((metric, tenant_id, timeframe))

    async def cost_breakdown(self, *, tenant_id: UUID, timeframe: str) -> dict[str, object]:
        self._record("cost", tenant_id, timeframe)
        return {
            "tenant_id": str(tenant_id),
            "timeframe": timeframe,
            "series": [],
            "summary": {"total_cost": 0, "total_tokens": 0, "total_requests": len(self.calls)},
        }

    async def version_performance(
        self,
        *,
        tenant_id: UUID,
        timeframe: str,
    ) -> dict[str, object]:
        self._record("versions", tenant_id, timeframe)
        return {"timeframe": timeframe, "versions": []}

    async def compare_versions(
        self,
        *,
        tenant_id: UUID,
        timeframe: str,
        baseline_version: str,
        candidate_version: str,
    ) -> dict[str, object]:
        self._record("comparison", tenant_id, timeframe)
        return {
            "timeframe": timeframe,
            "baseline": {"prompt_version": baseline_version},
            "candidate": {"prompt_version": candidate_version},
            "delta": {},
        }

    async def quality_drift(
        self,
        *,
        tenant_id: UUID,
        timeframe: str,
    ) -> dict[str, object]:
        self._record("quality-drift", tenant_id, timeframe)
        return {"timeframe": timeframe, "series": [], "alerts": []}


def _analytics_app(
    service: _RouterService,
    tenant_holder: dict[str, UUID],
) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_holder["tenant_id"]
    app.dependency_overrides[get_analytics_service] = lambda: service
    return app


@pytest.mark.asyncio
async def test_route_cache_isolated_by_tenant_and_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    tenant_holder = {"tenant_id": tenant_a}
    service = _RouterService()
    cache = _RecordingRouteCache()
    app = _analytics_app(service, tenant_holder)

    monkeypatch.setattr("src.core.cache.get_cache_service", lambda: cache)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/api/v1/ai/analytics/cost?timeframe=7d")
        same = await client.get("/api/v1/ai/analytics/cost?timeframe=7d")
        tenant_holder["tenant_id"] = tenant_b
        other_tenant = await client.get("/api/v1/ai/analytics/cost?timeframe=7d")
        other_query = await client.get("/api/v1/ai/analytics/cost?timeframe=30d")

    assert first.status_code == 200
    assert same.json() == first.json()
    assert other_tenant.json()["tenant_id"] == str(tenant_b)
    assert other_query.json()["timeframe"] == "30d"
    assert [call[0] for call in service.calls] == ["cost", "cost", "cost"]
    assert [call[1] for call in service.calls] == [tenant_a, tenant_b, tenant_b]
    assert [call[2] for call in service.calls] == ["7d", "7d", "30d"]
    assert len({key for key, _ in cache.set_calls}) == 3
    assert all(ttl == 300 for _, ttl in cache.set_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "metric"),
    [
        ("/api/v1/ai/analytics/cost?timeframe=bad", "cost"),
        ("/api/v1/ai/analytics/versions?timeframe=bad", "versions"),
        (
            "/api/v1/ai/analytics/comparison"
            "?baseline_version=v1&candidate_version=v2&timeframe=bad",
            "comparison",
        ),
        ("/api/v1/ai/analytics/quality-drift?timeframe=bad", "quality-drift"),
    ],
)
async def test_all_analytics_routes_map_service_validation_to_400(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    metric: str,
) -> None:
    tenant_holder = {"tenant_id": uuid4()}
    service = _RouterService()
    service.raise_value_error = True
    app = _analytics_app(service, tenant_holder)

    monkeypatch.setattr("src.core.cache.get_cache_service", lambda: None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid timeframe"
    assert service.calls == []


@pytest.mark.asyncio
async def test_router_success_contracts_for_versions_comparison_and_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    tenant_holder = {"tenant_id": tenant_id}
    service = _RouterService()
    app = _analytics_app(service, tenant_holder)

    monkeypatch.setattr("src.core.cache.get_cache_service", lambda: None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        versions = await client.get("/api/v1/ai/analytics/versions?timeframe=30d")
        comparison = await client.get(
            "/api/v1/ai/analytics/comparison"
            "?baseline_version=v1&candidate_version=v2&timeframe=30d"
        )
        drift = await client.get("/api/v1/ai/analytics/quality-drift?timeframe=30d")

    assert versions.status_code == comparison.status_code == drift.status_code == 200
    assert [call[0] for call in service.calls] == [
        "versions",
        "comparison",
        "quality-drift",
    ]
    assert all(call[1] == tenant_id for call in service.calls)
