"""
C2Pro - Cache Layer

Redis/Upstash cache with SSL/TLS support and safe in-memory fallback.

This module provides a robust caching layer with the following features:
- Asynchronous Redis client with connection pooling
- SSL/TLS support for Upstash and production environments
- Automatic JSON serialization/deserialization
- Soft failure: if Redis is unavailable, falls back to in-memory cache
- Namespace support with key prefixes (e.g., c2pro:project:{id}:...)
- TTL (Time To Live) support for automatic expiration
- Metrics integration for cache hit/miss tracking

Usage:
    from src.core.cache import get_cache_service

    cache = get_cache_service()
    await cache.set("user:123", {"name": "John"}, ttl=300)
    data = await cache.get("user:123")
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

import redis.asyncio as redis
import structlog
from redis.exceptions import RedisError

from src.config import settings
from src.core.observability import record_cache_hit, record_cache_miss

logger = structlog.get_logger()

# Cache type constants
CACHE_TYPE_EXTRACTION = "document_extraction"
CACHE_TYPE_PROJECT = "project"
CACHE_TYPE_ANALYSIS = "analysis"

# TTL constants (in seconds)
EXTRACTION_TTL_SECONDS = 60 * 60 * 24  # 24 hours
PROJECT_TTL_SECONDS = 60 * 60  # 1 hour
ANALYSIS_TTL_SECONDS = 60 * 30  # 30 minutes

# Namespace prefixes
NAMESPACE_C2PRO = "c2pro"
NAMESPACE_PROJECT = "project"
NAMESPACE_USER = "user"
NAMESPACE_SESSION = "session"
NAMESPACE_RATE_LIMIT = "ratelimit"


class InMemoryCache:
    """
    In-memory cache fallback implementation.

    Used when Redis is unavailable or not configured.
    Provides TTL support using monotonic time for expiration.
    """

    def __init__(self) -> None:
        self._items: dict[str, tuple[bytes, float | None]] = {}

    async def get(self, key: str) -> bytes | None:
        """Get value from cache by key."""
        entry = self._items.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            self._items.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: bytes, ttl_seconds: int | None) -> None:
        """Set value in cache with optional TTL."""
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = time.monotonic() + ttl_seconds
        self._items[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        """Delete key from cache. Returns True if key existed."""
        return self._items.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        entry = self._items.get(key)
        if not entry:
            return False
        _, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            self._items.pop(key, None)
            return False
        return True

    async def close(self) -> None:
        """Clear all cached items."""
        self._items.clear()


class CacheService:
    """
    Robust Redis cache service with soft failure fallback.

    Features:
    - Async Redis client with SSL/TLS support
    - Automatic fallback to in-memory cache on Redis failures
    - JSON serialization/deserialization
    - Namespace support with key prefixes
    - TTL (Time To Live) for automatic expiration
    - Metrics tracking for cache operations

    The service NEVER crashes the application if Redis is unavailable.
    It logs errors and gracefully degrades to in-memory cache.
    """

    def __init__(self, redis_url: Optional[str] = None, namespace_prefix: str = NAMESPACE_C2PRO) -> None:
        """
        Initialize cache service.

        Args:
            redis_url: Redis connection URL. Supports redis:// and rediss:// (SSL/TLS).
                       If None, only in-memory cache will be used.
            namespace_prefix: Default namespace prefix for all keys (default: "c2pro").
        """
        self._redis: Optional[redis.Redis] = None
        self._memory = InMemoryCache()
        self._enabled = bool(redis_url)
        self._namespace = namespace_prefix

        if redis_url:
            try:
                # Parse SSL/TLS configuration
                # rediss:// URLs automatically enable SSL
                ssl_enabled = redis_url.startswith("rediss://")

                # Create Redis client with proper SSL and connection pool settings
                self._redis = redis.from_url(
                    redis_url,
                    decode_responses=False,
                    encoding="utf-8",
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                    # SSL is automatically handled by rediss:// URLs
                )
                logger.info(
                    "cache_initialized",
                    backend="redis",
                    ssl_enabled=ssl_enabled,
                    namespace=self._namespace
                )
            except Exception as exc:
                logger.error("cache_init_failed", error=str(exc))
                self._redis = None
                self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if cache is enabled (Redis available)."""
        return self._enabled

    def _build_key(self, key: str, namespace: Optional[str] = None) -> str:
        """
        Build namespaced cache key.

        Args:
            key: Base key name
            namespace: Optional namespace override. If None, uses default namespace.

        Returns:
            Fully qualified key with namespace prefix.

        Example:
            _build_key("user:123") -> "c2pro:user:123"
            _build_key("session:abc", "tenant:5") -> "tenant:5:session:abc"
        """
        ns = namespace if namespace is not None else self._namespace
        if ns:
            return f"{ns}:{key}"
        return key

    async def ping(self) -> bool:
        """
        Ping Redis to check connectivity.

        Returns:
            True if Redis is available, False otherwise.
        """
        if not self._redis:
            logger.info("cache_disabled", reason="redis_url_missing")
            return False
        try:
            await self._redis.ping()
            logger.info("cache_ready", backend="redis")
            self._enabled = True
            return True
        except RedisError as exc:
            logger.warning("cache_unavailable", error=str(exc))
            self._enabled = False
            return False

    async def close(self) -> None:
        """Close Redis connection and clear in-memory cache."""
        if self._redis:
            try:
                await self._redis.close()
                await self._redis.connection_pool.disconnect()
            except Exception as exc:
                logger.warning("cache_close_failed", error=str(exc))
        await self._memory.close()

    # =============================================
    # Core Methods (Public API)
    # =============================================

    async def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        default: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Get value from cache (auto-deserializes JSON).

        Args:
            key: Cache key
            namespace: Optional namespace override
            default: Default value if key not found

        Returns:
            Cached value (deserialized from JSON) or default

        Example:
            user = await cache.get("user:123")
            project = await cache.get("project:456", namespace="tenant:5")
        """
        full_key = self._build_key(key, namespace)
        value = await self.get_json(full_key)
        return value if value is not None else default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Set value in cache (auto-serializes to JSON).

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds (None = no expiration)
            namespace: Optional namespace override

        Returns:
            True if set successfully, False otherwise

        Example:
            await cache.set("user:123", {"name": "John"}, ttl=300)
            await cache.set("session:abc", session_data, ttl=3600, namespace="sessions")
        """
        full_key = self._build_key(key, namespace)
        try:
            await self.set_json(full_key, value, ttl)
            return True
        except Exception as exc:
            logger.warning("cache_set_failed", key=full_key, error=str(exc))
            return False

    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete
            namespace: Optional namespace override

        Returns:
            True if key was deleted, False if key didn't exist

        Example:
            await cache.delete("user:123")
            await cache.delete("session:abc", namespace="sessions")
        """
        full_key = self._build_key(key, namespace)

        if self._redis:
            try:
                result = await self._redis.delete(full_key)
                return result > 0
            except RedisError as exc:
                logger.warning("cache_delete_failed", key=full_key, error=str(exc))

        return await self._memory.delete(full_key)

    async def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key to check
            namespace: Optional namespace override

        Returns:
            True if key exists, False otherwise

        Example:
            if await cache.exists("user:123"):
                user = await cache.get("user:123")
        """
        full_key = self._build_key(key, namespace)

        if self._redis:
            try:
                result = await self._redis.exists(full_key)
                return result > 0
            except RedisError as exc:
                logger.warning("cache_exists_failed", key=full_key, error=str(exc))

        return await self._memory.exists(full_key)

    # =============================================
    # Internal Methods (Bytes Level)
    # =============================================

    async def _get_bytes(self, key: str) -> Optional[bytes]:
        """Internal method to get raw bytes from cache."""
        if self._redis:
            try:
                value = await self._redis.get(key)
                if value is None:
                    return None
                if isinstance(value, bytes):
                    return value
                return str(value).encode("utf-8")
            except RedisError as exc:
                logger.warning("cache_read_failed", key=key, error=str(exc))
        return await self._memory.get(key)

    async def _set_bytes(self, key: str, value: bytes, ttl_seconds: Optional[int]) -> None:
        """Internal method to set raw bytes in cache."""
        if self._redis:
            try:
                await self._redis.set(key, value, ex=ttl_seconds)
                return
            except RedisError as exc:
                logger.warning("cache_write_failed", key=key, error=str(exc))
        await self._memory.set(key, value, ttl_seconds)

    # =============================================
    # JSON Serialization Methods
    # =============================================

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Get and deserialize JSON value from cache.

        Args:
            key: Cache key (should already be namespaced)

        Returns:
            Deserialized Python object or None if not found/invalid
        """
        payload = await self._get_bytes(key)
        if payload is None:
            return None
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("cache_decode_failed", key=key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: Optional[int]) -> None:
        """
        Serialize and store JSON value in cache.

        Args:
            key: Cache key (should already be namespaced)
            value: Python object to serialize (must be JSON-serializable)
            ttl_seconds: Time to live in seconds (None = no expiration)
        """
        payload = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        await self._set_bytes(key, payload, ttl_seconds)

    # =============================================
    # Domain-Specific Methods (Document Extraction)
    # =============================================

    async def get_extraction(
        self,
        document_hash: str,
        task_type: str
    ) -> Optional[dict[str, Any]]:
        """
        Get cached document extraction result.

        Args:
            document_hash: SHA256 hash of document content
            task_type: Type of extraction task

        Returns:
            Cached extraction result or None if not found
        """
        key = build_extraction_cache_key(document_hash, task_type)
        payload = await self.get_json(key)
        if payload is None:
            record_cache_miss(CACHE_TYPE_EXTRACTION)
            return None
        record_cache_hit(CACHE_TYPE_EXTRACTION)
        return payload

    async def set_extraction(
        self,
        document_hash: str,
        task_type: str,
        payload: dict[str, Any],
        ttl_seconds: Optional[int] = EXTRACTION_TTL_SECONDS,
    ) -> None:
        """
        Cache document extraction result.

        Args:
            document_hash: SHA256 hash of document content
            task_type: Type of extraction task
            payload: Extraction result to cache
            ttl_seconds: Time to live (default: 24 hours)
        """
        key = build_extraction_cache_key(document_hash, task_type)
        await self.set_json(key, payload, ttl_seconds)


# =============================================
# Utility Functions
# =============================================


def build_document_hash(content: bytes) -> str:
    """
    Generate SHA256 hash of document content.

    Args:
        content: Raw document bytes

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(content).hexdigest()


def build_extraction_cache_key(document_hash: str, task_type: str) -> str:
    """
    Build cache key for document extraction results.

    Args:
        document_hash: SHA256 hash of document
        task_type: Type of extraction (e.g., "clauses", "metadata")

    Returns:
        Formatted cache key: "extraction:{task_type}:{document_hash}"
    """
    return f"extraction:{task_type}:{document_hash}"


def build_project_cache_key(project_id: str, resource: str) -> str:
    """
    Build cache key for project resources.

    Args:
        project_id: Project UUID
        resource: Resource type (e.g., "summary", "analysis")

    Returns:
        Formatted cache key: "project:{project_id}:{resource}"
    """
    return f"{NAMESPACE_PROJECT}:{project_id}:{resource}"


def build_rate_limit_key(user_id: str, endpoint: str) -> str:
    """
    Build cache key for rate limiting.

    Args:
        user_id: User UUID
        endpoint: API endpoint path

    Returns:
        Formatted cache key: "ratelimit:{user_id}:{endpoint}"
    """
    return f"{NAMESPACE_RATE_LIMIT}:{user_id}:{endpoint}"


# =============================================
# Singleton Instance (Dependency Injection)
# =============================================

_cache_service: Optional[CacheService] = None


async def init_cache(namespace_prefix: str = NAMESPACE_C2PRO) -> CacheService:
    """
    Initialize the cache service singleton.

    This should be called during application startup (in lifespan).

    Args:
        namespace_prefix: Default namespace for cache keys

    Returns:
        Initialized CacheService instance

    Example:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await init_cache()
            yield
            await close_cache()
    """
    global _cache_service
    _cache_service = CacheService(settings.redis_url, namespace_prefix=namespace_prefix)
    await _cache_service.ping()
    logger.info("cache_service_initialized", namespace=namespace_prefix)
    return _cache_service


def get_cache_service() -> Optional[CacheService]:
    """
    Get the cache service singleton instance.

    Returns:
        CacheService instance or None if not initialized

    Example:
        cache = get_cache_service()
        if cache:
            await cache.set("key", value, ttl=300)
    """
    return _cache_service


async def close_cache() -> None:
    """
    Close the cache service and clean up resources.

    This should be called during application shutdown (in lifespan).
    """
    global _cache_service
    if _cache_service is None:
        return
    await _cache_service.close()
    _cache_service = None
    logger.info("cache_service_closed")
