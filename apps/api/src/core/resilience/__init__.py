"""
Circuit Breaker Resilience Package.

Provides circuit breaker pattern implementation for protecting external service calls.

Quick Start:
    from src.core.resilience import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerRegistry,
        with_circuit_breaker,
    )

    # Using decorator (recommended)
    @with_circuit_breaker("openai_embeddings")
    async def embed_texts(texts: list[str]) -> list[list[float]]:
        ...

    # Using registry directly
    cb = CircuitBreakerRegistry.register(
        CircuitBreakerConfig(service_name="my_service", failure_threshold=5)
    )

    if await cb.can_execute():
        try:
            result = await external_call()
            await cb.record_success()
        except Exception as e:
            await cb.record_failure(e)
            raise

    # Check health status
    status = CircuitBreakerRegistry.get_all_health_status()
"""

from src.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    CircuitBreakerStats,
)
from src.core.resilience.config import (
    CircuitBreakerSettings,
    get_circuit_breaker_settings,
)
from src.core.resilience.decorators import (
    with_circuit_breaker,
    with_circuit_breaker_sync,
)
from src.core.resilience.registry import CircuitBreakerRegistry

__all__ = [
    # Core classes
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
    "CircuitBreakerStats",
    # Registry
    "CircuitBreakerRegistry",
    # Configuration
    "CircuitBreakerSettings",
    "get_circuit_breaker_settings",
    # Decorators
    "with_circuit_breaker",
    "with_circuit_breaker_sync",
]
