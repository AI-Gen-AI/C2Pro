from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import CacheService
from src.core.json_types import JsonDict

logger = structlog.get_logger()


def _parse_timeframe(timeframe: str) -> timedelta:
    raw = timeframe.strip().lower()
    if raw.endswith("d") and raw[:-1].isdigit():
        return timedelta(days=int(raw[:-1]))
    if raw.endswith("h") and raw[:-1].isdigit():
        return timedelta(hours=int(raw[:-1]))
    if raw.endswith("w") and raw[:-1].isdigit():
        return timedelta(weeks=int(raw[:-1]))
    raise ValueError("Invalid timeframe. Use formats like 24h, 7d, 30d, 12w")


class AIAnalyticsService:
    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self._db = db
        self._cache = cache

    @staticmethod
    def _cache_key(*, tenant_id: UUID, metric: str, timeframe: str, scope: str = "default") -> str:
        return f"analytics:{tenant_id}:{metric}:{timeframe}:{scope}"

    async def _get_cached(self, key: str) -> JsonDict | None:
        if self._cache is None:
            return None
        try:
            return cast(JsonDict | None, await self._cache.get(key))
        except Exception as exc:
            logger.warning("analytics_cache_get_failed", cache_key=key, error=str(exc))
            return None

    async def _set_cached(self, key: str, payload: JsonDict, ttl_seconds: int) -> None:
        if self._cache is None:
            return
        try:
            await self._cache.set(key, payload, ttl=ttl_seconds)
        except Exception as exc:
            logger.warning("analytics_cache_set_failed", cache_key=key, error=str(exc))

    async def invalidate_tenant_analytics(self, tenant_id: UUID) -> None:
        if self._cache is None:
            return
        timeframes = ("24h", "7d", "30d", "90d")
        metrics = ("cost", "versions", "quality-drift")
        for timeframe in timeframes:
            for metric in metrics:
                await self._cache.delete(self._cache_key(tenant_id=tenant_id, metric=metric, timeframe=timeframe))

    async def cost_breakdown(self, *, tenant_id: UUID, timeframe: str) -> JsonDict:
        key = self._cache_key(tenant_id=tenant_id, metric="cost", timeframe=timeframe)
        if cached := await self._get_cached(key):
            return cached

        window_start = datetime.now(UTC) - _parse_timeframe(timeframe)
        query = text(
            """
            SELECT
              date_trunc('day', created_at) AS bucket,
              model_name,
              COALESCE(log_metadata->>'prompt_version', 'unknown') AS prompt_version,
              COUNT(*)::int AS request_count,
              COALESCE(SUM(total_tokens), 0)::bigint AS total_tokens,
              COALESCE(SUM(estimated_cost), 0)::float8 AS total_cost,
              COALESCE(AVG(duration_ms), 0)::float8 AS avg_latency_ms
            FROM ai_usage_logs
            WHERE tenant_id = :tenant_id
              AND created_at >= :window_start
            GROUP BY 1,2,3
            ORDER BY bucket ASC
            """
        )
        result = await self._db.execute(query, {"tenant_id": tenant_id, "window_start": window_start})
        rows = [dict(row) for row in result.mappings().all()]

        summary_query = text(
            """
            SELECT
              COALESCE(SUM(estimated_cost), 0)::float8 AS total_cost,
              COALESCE(SUM(total_tokens), 0)::bigint AS total_tokens,
              COUNT(*)::int AS total_requests
            FROM ai_usage_logs
            WHERE tenant_id = :tenant_id
              AND created_at >= :window_start
            """
        )
        summary_result = await self._db.execute(summary_query, {"tenant_id": tenant_id, "window_start": window_start})
        summary = dict(summary_result.mappings().one())

        payload = {
            "timeframe": timeframe,
            "window_start": window_start.isoformat(),
            "series": [
                {
                    "bucket": row["bucket"].isoformat() if row["bucket"] else None,
                    "model": row["model_name"],
                    "prompt_version": row["prompt_version"],
                    "request_count": row["request_count"],
                    "total_tokens": int(row["total_tokens"]),
                    "total_cost": float(row["total_cost"]),
                    "avg_latency_ms": float(row["avg_latency_ms"]),
                }
                for row in rows
            ],
            "summary": {
                "total_cost": float(summary["total_cost"]),
                "total_tokens": int(summary["total_tokens"]),
                "total_requests": int(summary["total_requests"]),
            },
        }
        await self._set_cached(key, payload, ttl_seconds=15 * 60)
        return payload

    async def version_performance(self, *, tenant_id: UUID, timeframe: str) -> JsonDict:
        key = self._cache_key(tenant_id=tenant_id, metric="versions", timeframe=timeframe)
        if cached := await self._get_cached(key):
            return cached

        window_start = datetime.now(UTC) - _parse_timeframe(timeframe)
        query = text(
            """
            SELECT
              COALESCE(log_metadata->>'prompt_version', 'unknown') AS prompt_version,
              COALESCE(log_metadata->>'prompt_tag', 'untagged') AS prompt_tag,
              COUNT(*)::int AS total_runs,
              COUNT(*) FILTER (WHERE status IN ('success','cached'))::int AS success_runs,
              COALESCE(AVG(duration_ms), 0)::float8 AS avg_latency_ms,
              COALESCE(SUM(estimated_cost), 0)::float8 AS total_cost,
              COUNT(*) FILTER (WHERE log_metadata ? 'feedback_score')::int AS feedback_count,
              COALESCE(AVG((log_metadata->>'feedback_score')::float), 0)::float8 AS avg_feedback_score
            FROM ai_usage_logs
            WHERE tenant_id = :tenant_id
              AND created_at >= :window_start
            GROUP BY 1,2
            ORDER BY total_runs DESC, prompt_version ASC
            """
        )
        result = await self._db.execute(query, {"tenant_id": tenant_id, "window_start": window_start})
        rows = [dict(row) for row in result.mappings().all()]
        payload = {
            "timeframe": timeframe,
            "window_start": window_start.isoformat(),
            "versions": [
                {
                    "prompt_version": row["prompt_version"],
                    "prompt_tag": row["prompt_tag"],
                    "total_runs": row["total_runs"],
                    "success_runs": row["success_runs"],
                    "success_rate": (row["success_runs"] / row["total_runs"]) if row["total_runs"] else 0,
                    "avg_latency_ms": float(row["avg_latency_ms"]),
                    "total_cost": float(row["total_cost"]),
                    "feedback_count": row["feedback_count"],
                    "avg_feedback_score": float(row["avg_feedback_score"]),
                }
                for row in rows
            ],
        }
        await self._set_cached(key, payload, ttl_seconds=30 * 60)
        return payload

    async def compare_versions(
        self,
        *,
        tenant_id: UUID,
        timeframe: str,
        baseline_version: str,
        candidate_version: str,
    ) -> JsonDict:
        compare_scope = hashlib.sha1(f"{baseline_version}:{candidate_version}".encode()).hexdigest()[:12]
        key = self._cache_key(
            tenant_id=tenant_id,
            metric="comparison",
            timeframe=timeframe,
            scope=compare_scope,
        )
        if cached := await self._get_cached(key):
            return cached

        window_start = datetime.now(UTC) - _parse_timeframe(timeframe)
        query = text(
            """
            SELECT
              COALESCE(log_metadata->>'prompt_version', 'unknown') AS prompt_version,
              COUNT(*)::int AS total_runs,
              COUNT(*) FILTER (WHERE status IN ('success','cached'))::int AS success_runs,
              COALESCE(AVG(duration_ms), 0)::float8 AS avg_latency_ms,
              COALESCE(SUM(estimated_cost), 0)::float8 AS total_cost,
              COALESCE(AVG((log_metadata->>'feedback_score')::float), 0)::float8 AS avg_feedback_score
            FROM ai_usage_logs
            WHERE tenant_id = :tenant_id
              AND created_at >= :window_start
              AND COALESCE(log_metadata->>'prompt_version', 'unknown') IN (:baseline, :candidate)
            GROUP BY 1
            """
        )
        result = await self._db.execute(
            query,
            {
                "tenant_id": tenant_id,
                "window_start": window_start,
                "baseline": baseline_version,
                "candidate": candidate_version,
            },
        )
        rows = {row["prompt_version"]: dict(row) for row in result.mappings().all()}

        def _normalize(version: str) -> dict[str, Any]:
            row = rows.get(version)
            if row is None:
                return {
                    "prompt_version": version,
                    "total_runs": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_cost": 0.0,
                    "avg_feedback_score": 0.0,
                }
            total_runs = int(row["total_runs"])
            success_runs = int(row["success_runs"])
            return {
                "prompt_version": version,
                "total_runs": total_runs,
                "success_rate": (success_runs / total_runs) if total_runs else 0.0,
                "avg_latency_ms": float(row["avg_latency_ms"]),
                "total_cost": float(row["total_cost"]),
                "avg_feedback_score": float(row["avg_feedback_score"]),
            }

        baseline = _normalize(baseline_version)
        candidate = _normalize(candidate_version)
        payload = {
            "timeframe": timeframe,
            "baseline": baseline,
            "candidate": candidate,
            "delta": {
                "success_rate": candidate["success_rate"] - baseline["success_rate"],
                "avg_latency_ms": candidate["avg_latency_ms"] - baseline["avg_latency_ms"],
                "total_cost": candidate["total_cost"] - baseline["total_cost"],
                "avg_feedback_score": candidate["avg_feedback_score"] - baseline["avg_feedback_score"],
            },
        }
        await self._set_cached(key, payload, ttl_seconds=30 * 60)
        return payload

    async def quality_drift(self, *, tenant_id: UUID, timeframe: str) -> JsonDict:
        key = self._cache_key(tenant_id=tenant_id, metric="quality-drift", timeframe=timeframe)
        if cached := await self._get_cached(key):
            return cached

        window_start = datetime.now(UTC) - _parse_timeframe(timeframe)
        query = text(
            """
            SELECT
              date_trunc('day', created_at) AS bucket,
              operation_type,
              COUNT(*)::int AS run_count,
              COALESCE(AVG(duration_ms), 0)::float8 AS avg_latency_ms,
              COALESCE(AVG((log_metadata->>'feedback_score')::float), 0)::float8 AS avg_feedback_score,
              COUNT(*) FILTER (WHERE log_metadata ? 'feedback_score')::int AS feedback_count
            FROM ai_usage_logs
            WHERE tenant_id = :tenant_id
              AND created_at >= :window_start
            GROUP BY 1,2
            ORDER BY bucket ASC
            """
        )
        result = await self._db.execute(query, {"tenant_id": tenant_id, "window_start": window_start})
        rows = [dict(row) for row in result.mappings().all()]

        alerts: list[dict[str, Any]] = []
        by_operation: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_operation.setdefault(row["operation_type"], []).append(row)

        for operation, points in by_operation.items():
            for idx in range(1, len(points)):
                prev = points[idx - 1]
                curr = points[idx]
                if prev["avg_feedback_score"] > 0 and curr["avg_feedback_score"] > 0:
                    drop_ratio = (prev["avg_feedback_score"] - curr["avg_feedback_score"]) / prev["avg_feedback_score"]
                    if drop_ratio >= 0.25:
                        alerts.append(
                            {
                                "severity": "high",
                                "type": "feedback_drop",
                                "operation": operation,
                                "bucket": curr["bucket"].isoformat() if curr["bucket"] else None,
                                "message": f"Feedback dropped {drop_ratio:.0%} vs previous bucket",
                            }
                        )
                if prev["avg_latency_ms"] > 0:
                    latency_jump = (curr["avg_latency_ms"] - prev["avg_latency_ms"]) / prev["avg_latency_ms"]
                    if latency_jump >= 0.30:
                        alerts.append(
                            {
                                "severity": "medium",
                                "type": "latency_spike",
                                "operation": operation,
                                "bucket": curr["bucket"].isoformat() if curr["bucket"] else None,
                                "message": f"Latency increased {latency_jump:.0%} vs previous bucket",
                            }
                        )

        payload = {
            "timeframe": timeframe,
            "window_start": window_start.isoformat(),
            "series": [
                {
                    "bucket": row["bucket"].isoformat() if row["bucket"] else None,
                    "operation": row["operation_type"],
                    "run_count": row["run_count"],
                    "avg_latency_ms": float(row["avg_latency_ms"]),
                    "avg_feedback_score": float(row["avg_feedback_score"]),
                    "feedback_count": row["feedback_count"],
                }
                for row in rows
            ],
            "alerts": alerts,
        }
        await self._set_cached(key, payload, ttl_seconds=15 * 60)
        return payload
