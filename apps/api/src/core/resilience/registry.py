"""
Circuit Breaker Registry.

Central registry for managing all circuit breaker instances.
Provides singleton access and health status aggregation.

Usage:
    from src.core.resilience import CircuitBreakerRegistry, CircuitBreakerConfig

    # Register a circuit breaker
    cb = CircuitBreakerRegistry.register(
        CircuitBreakerConfig(service_name="my_service", failure_threshold=5)
    )

    # Get existing circuit breaker
    cb = CircuitBreakerRegistry.get("my_service")

    # Get health status of all circuit breakers
    status = CircuitBreakerRegistry.get_all_health_status()
"""

from __future__ import annotations

from typing import Any

import structlog

from src.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = structlog.get_logger()


class CircuitBreakerRegistry:
    """
    Singleton registry for all circuit breakers.

    Provides centralized management of circuit breakers across the application.
    Thread-safe for registration and access.
    """

    _breakers: dict[str, CircuitBreaker] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, config: CircuitBreakerConfig) -> CircuitBreaker:
        """
        Register a new circuit breaker or return existing one.

        If a circuit breaker with the same service_name already exists,
        returns the existing instance (idempotent).

        Args:
            config: Configuration for the circuit breaker

        Returns:
            CircuitBreaker instance for the service
        """
        service_name = config.service_name

        if service_name in cls._breakers:
            logger.debug(
                "circuit_breaker_already_registered",
                service=service_name,
            )
            return cls._breakers[service_name]

        cb = CircuitBreaker(config)
        cls._breakers[service_name] = cb

        logger.info(
            "circuit_breaker_registered",
            service=service_name,
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
        )

        return cb

    @classmethod
    def get(cls, service_name: str) -> CircuitBreaker | None:
        """
        Get circuit breaker by service name.

        Args:
            service_name: Name of the service

        Returns:
            CircuitBreaker instance or None if not found
        """
        return cls._breakers.get(service_name)

    @classmethod
    def get_or_create(
        cls,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold_in_half_open: int = 2,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create a new one.

        Convenience method that creates a config internally.

        Args:
            service_name: Name of the service
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            success_threshold_in_half_open: Successes needed to close circuit
            excluded_exceptions: Exception types that don't trip the breaker

        Returns:
            CircuitBreaker instance
        """
        existing = cls.get(service_name)
        if existing:
            return existing

        config = CircuitBreakerConfig(
            service_name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold_in_half_open=success_threshold_in_half_open,
            excluded_exceptions=excluded_exceptions,
        )
        return cls.register(config)

    @classmethod
    def get_all(cls) -> dict[str, CircuitBreaker]:
        """
        Get all registered circuit breakers.

        Returns:
            Dictionary mapping service names to circuit breakers
        """
        return cls._breakers.copy()

    @classmethod
    def get_all_health_status(cls) -> dict[str, dict[str, Any]]:
        """
        Get health status of all circuit breakers.

        Useful for health check endpoints and monitoring.

        Returns:
            Dictionary mapping service names to their health status
        """
        return {
            name: cb.get_health_status()
            for name, cb in cls._breakers.items()
        }

    @classmethod
    def get_open_circuits(cls) -> list[str]:
        """
        Get list of service names with open circuits.

        Returns:
            List of service names that have open circuit breakers
        """
        from src.core.resilience.circuit_breaker import CircuitBreakerState

        return [
            name
            for name, cb in cls._breakers.items()
            if cb.state == CircuitBreakerState.OPEN
        ]

    @classmethod
    def reset(cls, service_name: str) -> bool:
        """
        Reset a specific circuit breaker.

        Args:
            service_name: Name of the service to reset

        Returns:
            True if reset was successful, False if service not found
        """
        cb = cls._breakers.get(service_name)
        if cb is None:
            return False

        cb.reset()
        logger.info(
            "circuit_breaker_reset_by_registry",
            service=service_name,
        )
        return True

    @classmethod
    def reset_all(cls) -> None:
        """
        Reset all circuit breakers.

        Useful for testing and recovery scenarios.
        """
        for _name, cb in cls._breakers.items():
            cb.reset()

        logger.info(
            "circuit_breakers_reset_all",
            count=len(cls._breakers),
        )

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered circuit breakers.

        WARNING: This removes all circuit breakers. Use with caution.
        Primarily intended for testing.
        """
        cls._breakers.clear()
        cls._initialized = False

        logger.info("circuit_breaker_registry_cleared")

    @classmethod
    def count(cls) -> int:
        """
        Get the number of registered circuit breakers.

        Returns:
            Number of registered circuit breakers
        """
        return len(cls._breakers)
