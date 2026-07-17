"""
Token revocation helpers with Redis-backed storage.

Refers to Suite ID: TS-E2E-SEC-TNT-001.
TASK-REV-015: Migrated from in-memory to Redis-backed store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from typing import TYPE_CHECKING

import jwt
import redis.asyncio as redis

from src.config import settings

if TYPE_CHECKING:
    from src.core.cache import CacheService

_REVOKED_TOKEN_PREFIX = "revoked_token:"
_memory_fallback: dict[str, datetime] = {}
_memory_lock = Lock()


def _token_fingerprint(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _get_cache_service() -> CacheService | None:
    from src.core.cache import get_cache_service

    return get_cache_service()


async def _get_redis_client() -> redis.Redis[bytes] | None:
    cache = _get_cache_service()
    if cache and cache._redis:
        return cache._redis
    return None


def revoke_token(token: str) -> None:
    """
    Synchronous token revocation using in-memory store.

    This is the primary revocation function for backward compatibility.
    For async contexts (FastAPI), use revoke_token_async() instead.
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
    fingerprint = _token_fingerprint(token)

    with _memory_lock:
        _memory_fallback[fingerprint] = expires_at
        _cleanup_expired_unlocked(datetime.now(UTC))


async def revoke_token_async(token: str) -> None:
    """
    Async token revocation using Redis with in-memory fallback.

    Prefer this for async contexts (FastAPI routes).
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
    fingerprint = _token_fingerprint(token)
    now = datetime.now(UTC)
    ttl_seconds = int((expires_at - now).total_seconds())

    if ttl_seconds <= 0:
        return

    redis_client = await _get_redis_client()
    if redis_client:
        try:
            key = f"{_REVOKED_TOKEN_PREFIX}{fingerprint}"
            await redis_client.set(key, "1", ex=ttl_seconds)
            return
        except Exception:
            pass

    with _memory_lock:
        _memory_fallback[fingerprint] = expires_at


def is_token_revoked(token: str) -> bool:
    """
    Synchronous check if token is revoked.

    Uses in-memory store. For async contexts, use is_token_revoked_async().
    """
    fingerprint = _token_fingerprint(token)
    now = datetime.now(UTC)

    with _memory_lock:
        expires_at = _memory_fallback.get(fingerprint)
        if expires_at is not None:
            if expires_at > now:
                return True
            else:
                del _memory_fallback[fingerprint]

    return False


async def is_token_revoked_async(token: str) -> bool:
    """
    Async check if token is revoked.

    Checks Redis first, falls back to in-memory store.
    Prefer this for async contexts (FastAPI middleware).
    """
    fingerprint = _token_fingerprint(token)
    now = datetime.now(UTC)

    redis_client = await _get_redis_client()
    if redis_client:
        try:
            key = f"{_REVOKED_TOKEN_PREFIX}{fingerprint}"
            exists = await redis_client.exists(key)
            if exists:
                return True
        except Exception:
            pass

    with _memory_lock:
        expires_at = _memory_fallback.get(fingerprint)
        if expires_at is not None:
            if expires_at > now:
                return True
            else:
                del _memory_fallback[fingerprint]

    return False


def _cleanup_expired_unlocked(now: datetime) -> None:
    """Clean up expired tokens (must hold _memory_lock)."""
    expired = [fp for fp, expires_at in _memory_fallback.items() if expires_at <= now]
    for fp in expired:
        _memory_fallback.pop(fp, None)


async def cleanup_expired_tokens() -> int:
    """
    Clean up expired tokens from in-memory fallback.

    Returns number of tokens cleaned up.
    """
    now = datetime.now(UTC)
    with _memory_lock:
        expired = [fp for fp, expires_at in _memory_fallback.items() if expires_at <= now]
        for fp in expired:
            _memory_fallback.pop(fp, None)
        return len(expired)
