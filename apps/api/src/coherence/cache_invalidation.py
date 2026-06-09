"""
Coherence cache invalidation event handlers (ADR-009 §G, spec §6).

Each handler accepts an async Redis client (``redis.asyncio.Redis`` or any
object exposing ``scan_iter`` / ``unlink`` with the same async interface) and
a context describing *what* changed.  The implementation:

- Uses ``UNLINK`` (non-blocking server-side deletion) instead of ``DEL``.
- Iterates via ``scan_iter(match=..., count=500)`` to avoid blocking Redis.
- Batches UNLINKs in groups of 500 keys per call.
- Emits a structlog event ``coherence.cache_invalidated`` for every handler
  invocation (including zero-key runs for idempotency tracking).
- Is idempotent: running twice with no matching keys returns 0 on the second
  call without error.
- Logs only tenant/project UUIDs — no raw user data.

References
----------
- ADR-009 §G  (cache invalidation strategy)
- Spec §6     docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md
- cache_keys  src.coherence.cache_keys  (prefix builders)

Redis client
------------
The handlers are typed against the ``redis.asyncio`` interface.  Pass either
the bare ``redis.asyncio.Redis`` client or the ``CacheService._redis`` attribute
from ``src.core.cache``.  Do NOT pass the ``CacheService`` wrapper directly —
it does not expose ``scan_iter`` or ``unlink``.

Example usage
-------------
    from src.core.cache import get_cache_service
    from src.coherence.cache_invalidation import on_flag_flip

    cache = get_cache_service()
    if cache and cache._redis:
        count = await on_flag_flip(cache._redis, tenant_id=tenant_id)

Suite ID: TS-UD-COH-CACHE-KEYS-001
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from src.coherence.cache_keys import (
    project_prefix,
    tenant_all_versions_prefix,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_BATCH_SIZE: int = 500  # keys per UNLINK call


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _unlink_pattern(redis_client: Any, pattern: str) -> int:
    """SCAN *pattern* and UNLINK all matching keys in batches of ``_BATCH_SIZE``.

    Parameters
    ----------
    redis_client:
        An async Redis client exposing ``scan_iter`` and ``unlink``.
    pattern:
        Redis glob pattern for SCAN (e.g. ``coherence:*:*:<tenant>:*``).

    Returns
    -------
    int
        Total number of keys unlinked.
    """
    batch: list[str] = []
    total_unlinked = 0

    async for redis_key in redis_client.scan_iter(match=pattern, count=_BATCH_SIZE):
        batch.append(redis_key)
        if len(batch) >= _BATCH_SIZE:
            await redis_client.unlink(*batch)
            total_unlinked += len(batch)
            batch = []

    if batch:
        await redis_client.unlink(*batch)
        total_unlinked += len(batch)

    return total_unlinked


# ---------------------------------------------------------------------------
# Public event handlers
# ---------------------------------------------------------------------------


async def on_flag_flip(redis_client: Any, *, tenant_id: UUID) -> int:
    """Invalidate all v1 + v2 coherence cache keys for a tenant.

    Triggered when the ``score_version`` feature flag is toggled for a tenant.
    Clears both ``coherence-v1`` and ``coherence-v2`` entries so the next
    request recomputes with the newly active scorer.

    Parameters
    ----------
    redis_client:
        Async Redis client (``redis.asyncio.Redis`` or compatible).
    tenant_id:
        The tenant whose coherence cache should be flushed.

    Returns
    -------
    int
        Total keys unlinked (0 if cache was already empty).
    """
    v1_prefix, v2_prefix = tenant_all_versions_prefix(tenant_id=tenant_id)

    total = 0
    total += await _unlink_pattern(redis_client, v1_prefix)
    total += await _unlink_pattern(redis_client, v2_prefix)

    logger.info(
        "coherence.cache_invalidated",
        trigger="flag_flip",
        tenant_id=str(tenant_id),
        keys_unlinked=total,
    )
    return total


async def on_result_persisted(
    redis_client: Any,
    *,
    tenant_id: UUID,
    project_id: UUID,
) -> int:
    """Invalidate all coherence cache keys for a specific project.

    Triggered after a new coherence scoring result is saved to the database.
    Clears all namespace/version cache entries for that project so subsequent
    dashboard/diagnostics requests fetch fresh data.

    Parameters
    ----------
    redis_client:
        Async Redis client (``redis.asyncio.Redis`` or compatible).
    tenant_id:
        The tenant that owns the project.
    project_id:
        The project whose cache should be invalidated.

    Returns
    -------
    int
        Total keys unlinked (0 if nothing was cached).
    """
    prefix = project_prefix(tenant_id=tenant_id, project_id=project_id)
    total = await _unlink_pattern(redis_client, prefix)

    logger.info(
        "coherence.cache_invalidated",
        trigger="result_persisted",
        tenant_id=str(tenant_id),
        project_id=str(project_id),
        keys_unlinked=total,
    )
    return total


async def on_deploy(redis_client: Any) -> int:
    """One-time purge of ALL ``coherence:*`` keys at deploy time.

    Intended to run once during the Phase A / Phase G deploy to flush any
    stale keys produced by pre-ECOA-v2 code paths.  Safe to run multiple
    times — returns 0 on subsequent calls when the cache is already empty.

    Parameters
    ----------
    redis_client:
        Async Redis client (``redis.asyncio.Redis`` or compatible).

    Returns
    -------
    int
        Total keys unlinked.
    """
    total = await _unlink_pattern(redis_client, "coherence:*")

    logger.info(
        "coherence.cache_invalidated",
        trigger="deploy",
        keys_unlinked=total,
    )
    return total


__all__ = [
    "on_deploy",
    "on_flag_flip",
    "on_result_persisted",
]
