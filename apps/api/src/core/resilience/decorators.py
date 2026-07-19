"""
Circuit Breaker Decorators.

Provides decorator-based API for applying circuit breakers to functions.

Usage:
    from src.core.resilience import with_circuit_breaker

    @with_circuit_breaker("openai_embeddings")
    async def embed_texts(texts: list[str]) -> list[list[float]]:
        # External API call
        ...

    @with_circuit_breaker("my_service", fallback=lambda: {"status": "degraded"})
    async def get_data() -> dict:
        # External API call with fallback
        ...
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, cast

import structlog

from src.core.resilience.circuit_breaker import CircuitBreakerOpenError
from src.core.resilience.config import get_circuit_breaker_settings
from src.core.resilience.registry import CircuitBreakerRegistry

logger = structlog.get_logger()

P = ParamSpec("P")
T = TypeVar("T")


def with_circuit_breaker(
    service_name: str,
    # Callable[..., Any]: tying the fallback to T makes mypy solve T=Never when
    # no fallback is passed, poisoning every decorated function's return type.
    fallback: Callable[..., Any] | None = None,
    failure_threshold: int | None = None,
    recovery_timeout: float | None = None,
    reraise: bool = True,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator to wrap async functions with circuit breaker protection.

    The decorator automatically registers the circuit breaker if it doesn't exist
    and wraps the function with can_execute/record_success/record_failure logic.

    Args:
        service_name: Unique identifier for the circuit breaker
        fallback: Optional fallback function to call when circuit is open.
                 Can be sync or async. If not provided and circuit is open,
                 raises CircuitBreakerOpenError.
        failure_threshold: Custom failure threshold (uses config default if None)
        recovery_timeout: Custom recovery timeout (uses config default if None)
        reraise: If True, re-raises exceptions after recording failure.
                If False with fallback, calls fallback on any exception.

    Returns:
        Decorated async function

    Example:
        @with_circuit_breaker("openai_embeddings")
        async def _embed_texts(texts: list[str]) -> list[list[float]]:
            async with httpx.AsyncClient() as client:
                response = await client.post(...)
                return response.json()

        @with_circuit_breaker(
            "cache_service",
            fallback=lambda key: None,
            failure_threshold=3,
            recovery_timeout=15.0,
        )
        async def get_cached_value(key: str) -> Any:
            return await redis.get(key)
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            settings = get_circuit_breaker_settings()

            # Skip circuit breaker if disabled globally
            if not settings.enable_circuit_breakers:
                return await func(*args, **kwargs)

            # Get or create circuit breaker
            cb = CircuitBreakerRegistry.get_or_create(
                service_name=service_name,
                failure_threshold=failure_threshold or 5,
                recovery_timeout=recovery_timeout or 60.0,
            )

            # Check if we can execute
            if not await cb.can_execute():
                await cb.record_rejection()

                if fallback is not None:
                    logger.warning(
                        "circuit_breaker_fallback",
                        service=service_name,
                        function=func.__name__,
                    )
                    fb_result = fallback(*args, **kwargs)
                    if hasattr(fb_result, "__await__"):
                        return cast(T, await fb_result)
                    return cast(T, fb_result)

                raise CircuitBreakerOpenError(
                    service_name,
                    cb._get_recovery_time_remaining(),
                )

            # Execute with circuit breaker tracking
            try:
                result = await func(*args, **kwargs)
                await cb.record_success()
                return result
            except Exception as e:
                await cb.record_failure(e)

                if not reraise and fallback is not None:
                    logger.warning(
                        "circuit_breaker_exception_fallback",
                        service=service_name,
                        function=func.__name__,
                        error=str(e),
                    )
                    fb_result = fallback(*args, **kwargs)
                    if hasattr(fb_result, "__await__"):
                        return cast(T, await fb_result)
                    return cast(T, fb_result)

                raise

        return wrapper

    return decorator


def with_circuit_breaker_sync(
    service_name: str,
    fallback: Callable[..., Any] | None = None,
    failure_threshold: int | None = None,
    recovery_timeout: float | None = None,
    reraise: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for synchronous functions with circuit breaker protection.

    Similar to with_circuit_breaker but for non-async functions.
    Uses sync versions of circuit breaker methods.

    Args:
        service_name: Unique identifier for the circuit breaker
        fallback: Optional fallback function (must be sync)
        failure_threshold: Custom failure threshold
        recovery_timeout: Custom recovery timeout
        reraise: If True, re-raises exceptions after recording failure

    Returns:
        Decorated sync function
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            settings = get_circuit_breaker_settings()

            if not settings.enable_circuit_breakers:
                return func(*args, **kwargs)

            cb = CircuitBreakerRegistry.get_or_create(
                service_name=service_name,
                failure_threshold=failure_threshold or 5,
                recovery_timeout=recovery_timeout or 60.0,
            )

            if not cb.can_execute_sync():
                if fallback is not None:
                    logger.warning(
                        "circuit_breaker_fallback_sync",
                        service=service_name,
                        function=func.__name__,
                    )
                    return cast(T, fallback(*args, **kwargs))

                raise CircuitBreakerOpenError(
                    service_name,
                    cb._get_recovery_time_remaining(),
                )

            try:
                result = func(*args, **kwargs)
                cb.record_success_sync()
                return result
            except Exception as e:
                cb.record_failure_sync(e)

                if not reraise and fallback is not None:
                    logger.warning(
                        "circuit_breaker_exception_fallback_sync",
                        service=service_name,
                        function=func.__name__,
                        error=str(e),
                    )
                    return cast(T, fallback(*args, **kwargs))

                raise

        return wrapper

    return decorator
