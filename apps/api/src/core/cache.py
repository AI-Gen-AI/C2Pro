"""TS-AI-020.

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
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, get_type_hints

import redis.asyncio as redis
import structlog
from redis.exceptions import RedisError

from src.config import settings
from src.core.observability import record_cache_hit, record_cache_miss
from src.core.resilience import CircuitBreakerConfig, CircuitBreakerRegistry
from src.core.resilience.config import get_circuit_breaker_settings

logger = structlog.get_logger()

# Cache type constants
CACHE_TYPE_EXTRACTION = "document_extraction"
CACHE_TYPE_PROJECT = "project"
CACHE_TYPE_ANALYSIS = "analysis"
CACHE_TYPE_AI_ANALYTICS = "ai_analytics"

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

    @staticmethod
    def _build_key(key: str, namespace: str | None = None) -> str:
        if namespace:
            return f"{namespace}:{key}"
        return key

    @staticmethod
    def _encode_value(value: Any) -> bytes:
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")

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

    async def incr(
        self,
        key: str,
        *,
        amount: int = 1,
        ttl_seconds: int | None = None,
        namespace: str | None = None,
    ) -> int:
        """Atomically increment an integer key in the in-memory fallback."""
        full_key = self._build_key(key, namespace)
        current = await self.get(full_key)
        new_value = int(current.decode("utf-8")) + amount if current is not None else amount
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = time.monotonic() + ttl_seconds
        elif full_key in self._items:
            _, expires_at = self._items[full_key]
        self._items[full_key] = (str(new_value).encode("utf-8"), expires_at)
        return new_value

    async def decr(
        self,
        key: str,
        *,
        amount: int = 1,
        namespace: str | None = None,
    ) -> int:
        """Atomically decrement an integer key, flooring at zero."""
        full_key = self._build_key(key, namespace)
        current = await self.get(full_key)
        new_value = max(0, (int(current.decode("utf-8")) if current is not None else 0) - amount)
        if new_value <= 0:
            self._items.pop(full_key, None)
            return 0
        _, expires_at = self._items.get(full_key, (b"", None))
        self._items[full_key] = (str(new_value).encode("utf-8"), expires_at)
        return new_value

    async def set_if_absent(
        self,
        key: str,
        value: Any,
        *,
        ttl_seconds: int,
        namespace: str | None = None,
    ) -> bool:
        """Atomically set a key only when it is absent."""
        full_key = self._build_key(key, namespace)
        if await self.exists(full_key):
            return False
        await self.set(full_key, self._encode_value(value), ttl_seconds)
        return True

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
    - Circuit breaker to prevent hammering failing Redis
    - JSON serialization/deserialization
    - Namespace support with key prefixes
    - TTL (Time To Live) for automatic expiration
    - Metrics tracking for cache operations

    The service NEVER crashes the application if Redis is unavailable.
    It logs errors and gracefully degrades to in-memory cache.
    """

    def __init__(self, redis_url: str | None = None, namespace_prefix: str = NAMESPACE_C2PRO) -> None:
        """
        Initialize cache service.

        Args:
            redis_url: Redis connection URL. Supports redis:// and rediss:// (SSL/TLS).
                       If None, only in-memory cache will be used.
            namespace_prefix: Default namespace prefix for all keys (default: "c2pro").
        """
        self._redis: redis.Redis | None = None
        self._memory = InMemoryCache()
        self._enabled = bool(redis_url)
        self._namespace = namespace_prefix
        self._circuit_breaker = self._init_circuit_breaker()

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
                    namespace=self._namespace,
                    circuit_breaker_enabled=True,
                )
            except Exception as exc:
                logger.error("cache_init_failed", error=str(exc))
                self._redis = None
                self._enabled = False

    def _init_circuit_breaker(self):
        """Initialize circuit breaker for Redis operations."""
        cb_settings = get_circuit_breaker_settings()
        if not cb_settings.enable_circuit_breakers:
            return None

        return CircuitBreakerRegistry.register(
            CircuitBreakerConfig(
                service_name="redis_cache",
                failure_threshold=cb_settings.redis_failure_threshold,
                recovery_timeout=cb_settings.redis_recovery_timeout,
            )
        )

    @property
    def enabled(self) -> bool:
        """Check if cache is enabled (Redis available)."""
        return self._enabled

    def _build_key(self, key: str, namespace: str | None = None) -> str:
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
        namespace: str | None = None,
        default: Any | None = None
    ) -> Any | None:
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
        ttl: int | None = None,
        namespace: str | None = None
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

    async def delete(self, key: str, namespace: str | None = None) -> bool:
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

        if await self._can_use_redis():
            try:
                result = await self._redis.delete(full_key)
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                return result > 0
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_delete_failed", key=full_key, error=str(exc))

        return await self._memory.delete(full_key)

    async def exists(self, key: str, namespace: str | None = None) -> bool:
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

        if await self._can_use_redis():
            try:
                result = await self._redis.exists(full_key)
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                return result > 0
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_exists_failed", key=full_key, error=str(exc))

        return await self._memory.exists(full_key)

    async def incr(
        self,
        key: str,
        *,
        amount: int = 1,
        ttl_seconds: int | None = None,
        namespace: str | None = None,
    ) -> int:
        """Atomically increment an integer cache key."""
        full_key = self._build_key(key, namespace)
        if await self._can_use_redis():
            try:
                assert self._redis is not None
                new_value = int(await self._redis.incrby(full_key, amount))
                if ttl_seconds and new_value == amount:
                    await self._redis.expire(full_key, ttl_seconds)
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                return new_value
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_incr_failed", key=full_key, error=str(exc))
        return await self._memory.incr(full_key, amount=amount, ttl_seconds=ttl_seconds)

    async def decr(
        self,
        key: str,
        *,
        amount: int = 1,
        namespace: str | None = None,
    ) -> int:
        """Atomically decrement an integer cache key, flooring at zero."""
        full_key = self._build_key(key, namespace)
        if await self._can_use_redis():
            try:
                assert self._redis is not None
                new_value = int(await self._redis.decrby(full_key, amount))
                if new_value <= 0:
                    await self._redis.delete(full_key)
                    new_value = 0
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                return new_value
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_decr_failed", key=full_key, error=str(exc))
        return await self._memory.decr(full_key, amount=amount)

    async def set_if_absent(
        self,
        key: str,
        value: Any,
        *,
        ttl_seconds: int,
        namespace: str | None = None,
    ) -> bool:
        """Atomically set a cache key only when it is absent."""
        full_key = self._build_key(key, namespace)
        if await self._can_use_redis():
            try:
                assert self._redis is not None
                was_set = bool(await self._redis.set(full_key, value, nx=True, ex=ttl_seconds))
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                return was_set
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_set_if_absent_failed", key=full_key, error=str(exc))
        return await self._memory.set_if_absent(
            full_key,
            value,
            ttl_seconds=ttl_seconds,
        )

    # =============================================
    # Internal Methods (Bytes Level)
    # =============================================

    async def _can_use_redis(self) -> bool:
        """Check if Redis is available and circuit breaker allows execution."""
        if not self._redis:
            return False
        if self._circuit_breaker is None:
            return True
        return await self._circuit_breaker.can_execute()

    async def _get_bytes(self, key: str) -> bytes | None:
        """Internal method to get raw bytes from cache with circuit breaker protection."""
        if await self._can_use_redis():
            try:
                value = await self._redis.get(key)
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                if value is None:
                    return None
                if isinstance(value, bytes):
                    return value
                return str(value).encode("utf-8")
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_read_failed", key=key, error=str(exc))
        return await self._memory.get(key)

    async def _set_bytes(self, key: str, value: bytes, ttl_seconds: int | None) -> None:
        """Internal method to set raw bytes in cache with circuit breaker protection."""
        if await self._can_use_redis():
            try:
                await self._redis.set(key, value, ex=ttl_seconds)
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                return
            except RedisError as exc:
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure(exc)
                logger.warning("cache_write_failed", key=key, error=str(exc))
        await self._memory.set(key, value, ttl_seconds)

    # =============================================
    # JSON Serialization Methods
    # =============================================

    async def get_json(self, key: str) -> Any | None:
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

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None) -> None:
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
    ) -> dict[str, Any] | None:
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
        ttl_seconds: int | None = EXTRACTION_TTL_SECONDS,
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


def build_endpoint_cache_key(*, endpoint: str, query_params: dict[str, Any], tenant_id: Any) -> str:
    """
    TS-AI-020: Build a stable route cache key from endpoint, query params, and tenant.
    """
    normalized_payload = {
        "endpoint": endpoint,
        "query_params": query_params,
        "tenant_id": str(tenant_id),
    }
    digest = hashlib.sha256(
        json.dumps(normalized_payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"endpoint:{endpoint.strip('/').replace('/', ':')}:{digest}"


def cached(*, ttl: int, endpoint: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    TS-AI-020: Cache async route responses by endpoint, query params, and tenant_id.

    The decorator intentionally fails open: cache outages never block the route.
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        signature = inspect.signature(func)
        type_hints = get_type_hints(func, include_extras=True)
        evaluated_parameters = [
            parameter.replace(annotation=type_hints.get(name, parameter.annotation))
            for name, parameter in signature.parameters.items()
        ]
        evaluated_signature = signature.replace(
            parameters=evaluated_parameters,
            return_annotation=type_hints.get("return", signature.return_annotation),
        )

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            tenant_id = bound.arguments.get("tenant_id")
            query_params = {
                key: value
                for key, value in bound.arguments.items()
                if key not in {"tenant_id", "service"} and not key.startswith("_")
            }
            cache_key = build_endpoint_cache_key(endpoint=endpoint, query_params=query_params, tenant_id=tenant_id)
            cache = get_cache_service()
            cache_type = f"{CACHE_TYPE_AI_ANALYTICS}:{endpoint.strip('/')}"

            if cache is not None:
                try:
                    cached_payload = await cache.get(cache_key)
                    if cached_payload is not None:
                        record_cache_hit(cache_type)
                        return cached_payload
                    record_cache_miss(cache_type)
                except Exception as exc:
                    logger.warning("route_cache_get_failed", endpoint=endpoint, cache_key=cache_key, error=str(exc))

            payload = await func(*args, **kwargs)

            if cache is not None:
                try:
                    await cache.set(cache_key, payload, ttl=ttl)
                except Exception as exc:
                    logger.warning("route_cache_set_failed", endpoint=endpoint, cache_key=cache_key, error=str(exc))

            return payload

        wrapper.__signature__ = evaluated_signature  # type: ignore[attr-defined]
        return wrapper

    return decorator


# =============================================
# Singleton Instance (Dependency Injection)
# =============================================

_cache_service: CacheService | None = None


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


def get_cache_service() -> CacheService | None:
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


def get_redis_client() -> redis.Redis | None:
    """
    Return the raw ``redis.asyncio.Redis`` client from the singleton CacheService.

    Use this when you need direct Redis protocol access (e.g. ``scan_iter``,
    ``unlink``) that the ``CacheService`` wrapper does not expose.

    Returns:
        The underlying ``redis.asyncio.Redis`` instance, or ``None`` when the
        cache has not been initialised or was initialised without a Redis URL.

    Example:
        from src.core.cache import get_redis_client
        from src.coherence.cache_invalidation import on_flag_flip

        redis = get_redis_client()
        if redis is not None:
            await on_flag_flip(redis, tenant_id=tenant_id)
    """
    svc = get_cache_service()
    if svc is None:
        return None
    return svc._redis


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
