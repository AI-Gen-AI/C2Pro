"""
ContentHashCache — generic SHA-256 key → FindingSignal cache for the LLM
semantic gate (P3).

Wraps the existing CacheService (Redis with in-memory fallback) to give the
gate a simple async get(key)/set(key, value) interface that respects the
content-hash key model the gate computes. The wrapper owns the namespace
prefix and TTL; the gate owns the key shape (rule_id + PROMPT_VERSION +
canonical clause text).
"""

from __future__ import annotations

from typing import Any

import structlog

from src.coherence.models import FindingSignal

logger = structlog.get_logger()

# 7 days — long enough that re-evaluations of an unchanged contract hit cache;
# short enough that schema drifts age out on their own.
_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
_NAMESPACE = "coherence.llm_gate"


class ContentHashCache:
    """Thin async key/value cache for FindingSignal, keyed by SHA-256 hex."""

    def __init__(self, cache_service: Any, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._svc = cache_service
        self._ttl = ttl_seconds

    @staticmethod
    def _ns_key(key: str) -> str:
        return f"{_NAMESPACE}:{key}"

    async def get(self, key: str) -> FindingSignal | None:
        if self._svc is None:
            return None
        try:
            raw = await self._svc.get_json(self._ns_key(key))
        except Exception as exc:  # noqa: BLE001 — cache must NEVER break scoring
            logger.warning("content_hash_cache.get_failed", key=key, err=str(exc))
            return None
        if raw is None:
            return None
        try:
            return FindingSignal(**raw)
        except Exception as exc:  # noqa: BLE001 — corrupt entry: treat as miss
            logger.warning("content_hash_cache.deserialize_failed", key=key, err=str(exc))
            return None

    async def set(self, key: str, value: FindingSignal) -> None:
        if self._svc is None:
            return
        try:
            payload = value.model_dump() if hasattr(value, "model_dump") else value.__dict__
            await self._svc.set_json(self._ns_key(key), payload, self._ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("content_hash_cache.set_failed", key=key, err=str(exc))


def get_content_hash_cache() -> ContentHashCache:
    """Factory: return a ContentHashCache backed by the singleton CacheService.

    `get_cache_service()` may return None when Redis is not configured; the
    wrapper handles None gracefully (every get() returns None → cache miss).
    """
    from src.core.cache import get_cache_service

    return ContentHashCache(cache_service=get_cache_service())
