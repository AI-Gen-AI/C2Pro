"""
C2Pro - Rate Limiting Middleware

Hierarchical rate limiter (user -> tenant) with Redis fixed window counters.
"""

from __future__ import annotations

from datetime import datetime
import time
from typing import Callable
from uuid import UUID

import redis.asyncio as redis
import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import jwt
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = structlog.get_logger()

DEFAULT_USER_LIMIT = 20
DEFAULT_TENANT_LIMIT = 60
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Hierarchical rate limiter (user -> tenant) with Redis fixed window counters.
    """

    PUBLIC_PATH_PREFIXES = (
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login",
        "/api/v1/auth/login",
    )

    def __init__(
        self,
        app,
        redis_url: str | None = None,
        user_limit: int | None = None,
        tenant_limit: int | None = None,
    ) -> None:
        super().__init__(app)
        self._redis = self._build_redis(redis_url or settings.redis_url)
        self._user_limit = user_limit or settings.rate_limit_user_per_min
        self._tenant_limit = tenant_limit or settings.rate_limit_tenant_per_min
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        if self._is_public_path(request.url.path):
            return await call_next(request)

        if self._redis is None:
            return await self._dispatch_in_memory(request, call_next)

        user_id, tenant_id = self._extract_ids(request)
        if user_id is None and tenant_id is None:
            return await self._dispatch_in_memory(request, call_next)

        now = datetime.utcnow()
        window_key = now.strftime("%Y-%m-%dT%H:%M")

        user_count, tenant_count = await self._increment_counters(
            user_id=user_id,
            tenant_id=tenant_id,
            window_key=window_key,
        )

        if user_count is None and tenant_count is None:
            return await self._dispatch_in_memory(request, call_next)

        reset_seconds = max(1, WINDOW_SECONDS - now.second)

        if user_count is not None and user_count > self._user_limit:
            logger.warning(
                "rate_limit_exceeded",
                scope="user",
                user_id=str(user_id),
                path=request.url.path,
                limit=self._user_limit,
                count=user_count,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "User limit exceeded"},
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit-User": str(self._user_limit),
                    "X-RateLimit-Remaining-User": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
            )

        if tenant_count is not None and tenant_count > self._tenant_limit:
            logger.warning(
                "rate_limit_exceeded",
                scope="tenant",
                tenant_id=str(tenant_id),
                path=request.url.path,
                limit=self._tenant_limit,
                count=tenant_count,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Tenant limit exceeded"},
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit-User": str(self._user_limit),
                    "X-RateLimit-Remaining-User": str(
                        max(0, self._user_limit - (user_count or 0))
                    ),
                    "X-RateLimit-Reset": str(reset_seconds),
                    "X-RateLimit-Limit-Tenant": str(self._tenant_limit),
                    "X-RateLimit-Remaining-Tenant": str(
                        max(0, self._tenant_limit - (tenant_count or 0))
                    ),
                },
            )

        response = await call_next(request)

        if user_count is not None:
            response.headers["X-RateLimit-Limit-User"] = str(self._user_limit)
            response.headers["X-RateLimit-Remaining-User"] = str(
                max(0, self._user_limit - user_count)
            )
            response.headers["X-RateLimit-Reset"] = str(reset_seconds)

        if tenant_count is not None:
            response.headers["X-RateLimit-Limit-Tenant"] = str(self._tenant_limit)
            response.headers["X-RateLimit-Remaining-Tenant"] = str(
                max(0, self._tenant_limit - tenant_count)
            )

        return response

    async def _dispatch_in_memory(self, request: Request, call_next: Callable) -> Response:
        client_id = self._get_client_identifier(request)
        if self._is_rate_limited(client_id, request.url.path):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        self._record_request(client_id)
        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES)

    def _build_redis(self, redis_url: str | None) -> redis.Redis | None:
        if not redis_url:
            logger.warning("rate_limiter_disabled", reason="redis_url_missing")
            return None
        try:
            return redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        except Exception as exc:
            logger.error("rate_limiter_init_failed", error=str(exc))
            return None

    def _extract_ids(self, request: Request) -> tuple[UUID | None, UUID | None]:
        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)

        if tenant_id or user_id:
            return user_id, tenant_id

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None, None

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_signature": True, "verify_exp": True},
            )
        except (jwt.PyJWTError, ValueError):
            return None, None

        tenant_id_raw = payload.get("tenant_id")
        user_id_raw = payload.get("sub")

        try:
            tenant_id = UUID(tenant_id_raw) if tenant_id_raw else None
        except ValueError:
            tenant_id = None

        try:
            user_id = UUID(user_id_raw) if user_id_raw else None
        except ValueError:
            user_id = None

        return user_id, tenant_id

    async def _increment_counters(
        self,
        user_id: UUID | None,
        tenant_id: UUID | None,
        window_key: str,
    ) -> tuple[int | None, int | None]:
        if self._redis is None:
            return None, None

        user_key = (
            f"rate_limit:user:{user_id}:{window_key}" if user_id is not None else None
        )
        tenant_key = (
            f"rate_limit:tenant:{tenant_id}:{window_key}" if tenant_id is not None else None
        )

        try:
            pipeline = self._redis.pipeline()
            order: list[str] = []

            if user_key:
                pipeline.incr(user_key)
                pipeline.expire(user_key, WINDOW_SECONDS)
                order.append("user")

            if tenant_key:
                pipeline.incr(tenant_key)
                pipeline.expire(tenant_key, WINDOW_SECONDS)
                order.append("tenant")

            results = await pipeline.execute()

            user_count = None
            tenant_count = None
            idx = 0
            for scope in order:
                if scope == "user":
                    user_count = int(results[idx])
                if scope == "tenant":
                    tenant_count = int(results[idx])
                idx += 2

            return user_count, tenant_count
        except RedisError as exc:
            logger.warning("rate_limiter_redis_error", error=str(exc))
            return None, None

    def _get_client_identifier(self, request: Request) -> str:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}"

        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            return f"ip:{ip}"

        if request.client:
            return f"ip:{request.client.host}"

        return "ip:unknown"

    def _record_request(self, client_id: str) -> None:
        now = time.time()
        window_seconds = 300
        window_start = now - window_seconds

        timestamps = self._requests.get(client_id, [])
        timestamps = [ts for ts in timestamps if ts > window_start]
        timestamps.append(now)
        self._requests[client_id] = timestamps

    def _is_rate_limited(self, client_id: str, path: str) -> bool:
        limit = settings.rate_limit_per_minute
        if "/api/ai/" in path:
            limit = max(1, limit // 2)

        now = time.time()
        window_start = now - 60
        timestamps = [ts for ts in self._requests.get(client_id, []) if ts > window_start]
        return len(timestamps) >= limit
