"""
Circuit Breaker Pattern Implementation.

Provides protection against cascading failures when external services
are unavailable or experiencing issues.

The circuit breaker has three states:
- CLOSED: Normal operation, requests flow through
- OPEN: Service is failing, requests are rejected immediately
- HALF_OPEN: Testing recovery, limited requests allowed

Usage:
    from src.core.resilience import CircuitBreaker, CircuitBreakerConfig

    cb = CircuitBreaker(CircuitBreakerConfig(service_name="my_service"))

    if await cb.can_execute():
        try:
            result = await external_call()
            await cb.record_success()
            return result
        except Exception as e:
            await cb.record_failure(e)
            raise
    else:
        raise CircuitBreakerOpenError("my_service")
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

import structlog

from src.core.observability.monitoring import (
    record_circuit_breaker_failure,
    record_circuit_breaker_rejection,
    record_circuit_breaker_state_change,
)

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitBreakerState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""

    def __init__(self, service_name: str, recovery_time_remaining: float | None = None):
        self.service_name = service_name
        self.recovery_time_remaining = recovery_time_remaining
        msg = f"Circuit breaker for '{service_name}' is open"
        if recovery_time_remaining is not None:
            msg += f" (recovery in {recovery_time_remaining:.1f}s)"
        super().__init__(msg)


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance."""

    service_name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold_in_half_open: int = 2
    excluded_exceptions: tuple[type[Exception], ...] = ()

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if self.success_threshold_in_half_open < 1:
            raise ValueError("success_threshold_in_half_open must be >= 1")


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_transitions: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    last_state_change_time: float | None = None


class CircuitBreaker:
    """
    Async-native circuit breaker implementation.

    Thread-safe using asyncio.Lock() for state management.
    Integrates with structlog for observability.
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count_in_half_open = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()
        self._stats = CircuitBreakerStats()

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Current failure count."""
        return self._failure_count

    async def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns True if circuit is CLOSED or HALF_OPEN (and timeout elapsed).
        Returns False if circuit is OPEN.
        """
        async with self._lock:
            if self._state == CircuitBreakerState.CLOSED:
                return True

            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
                    return True
                return False

            # HALF_OPEN: allow limited requests for testing
            return True

    def can_execute_sync(self) -> bool:
        """
        Synchronous version of can_execute for non-async contexts.

        Note: Not thread-safe without external synchronization.
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False

        return True

    async def record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            self._record_success_internal()

    def record_success_sync(self) -> None:
        """Synchronous version of record_success."""
        self._record_success_internal()

    def _record_success_internal(self) -> None:
        """Internal success recording logic."""
        self._stats.total_requests += 1
        self._stats.successful_requests += 1
        self._stats.last_success_time = time.time()

        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count_in_half_open += 1
            if self._success_count_in_half_open >= self.config.success_threshold_in_half_open:
                self._transition_to_closed()
        elif self._state == CircuitBreakerState.CLOSED:
            # Decay failure count on success
            self._failure_count = max(0, self._failure_count - 1)

    async def record_failure(self, exception: Exception) -> None:
        """
        Record a failed request.

        Args:
            exception: The exception that caused the failure.
                      If it's an excluded exception type, the circuit
                      breaker state is not affected.
        """
        async with self._lock:
            self._record_failure_internal(exception)

    def record_failure_sync(self, exception: Exception) -> None:
        """Synchronous version of record_failure."""
        self._record_failure_internal(exception)

    def _record_failure_internal(self, exception: Exception) -> None:
        """Internal failure recording logic."""
        self._stats.total_requests += 1
        self._stats.failed_requests += 1
        self._stats.last_failure_time = time.time()

        # Check if this exception type should be excluded
        if isinstance(exception, self.config.excluded_exceptions):
            logger.debug(
                "circuit_breaker_excluded_exception",
                service=self.config.service_name,
                exception_type=type(exception).__name__,
            )
            return

        self._failure_count += 1
        self._last_failure_time = time.time()

        # Record Prometheus metric
        record_circuit_breaker_failure(self.config.service_name)

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open state reopens the circuit
            self._transition_to_open()
        elif self._state == CircuitBreakerState.CLOSED and self._failure_count >= self.config.failure_threshold:
                self._transition_to_open()

    async def record_rejection(self) -> None:
        """Record a rejected request (circuit was open)."""
        async with self._lock:
            self._stats.total_requests += 1
            self._stats.rejected_requests += 1
            # Record Prometheus metric
            record_circuit_breaker_rejection(self.config.service_name)

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func if successful

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by func
        """
        if not await self.can_execute():
            await self.record_rejection()
            recovery_remaining = self._get_recovery_time_remaining()
            raise CircuitBreakerOpenError(self.config.service_name, recovery_remaining)

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if self._last_failure_time is None:
            return True
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.recovery_timeout

    def _get_recovery_time_remaining(self) -> float | None:
        """Get remaining time until recovery attempt."""
        if self._state != CircuitBreakerState.OPEN:
            return None
        if self._last_failure_time is None:
            return None
        elapsed = time.time() - self._last_failure_time
        remaining = self.config.recovery_timeout - elapsed
        return max(0, remaining)

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        old_state = self._state
        self._state = CircuitBreakerState.OPEN
        self._stats.state_transitions += 1
        self._stats.last_state_change_time = time.time()

        # Record Prometheus metric
        record_circuit_breaker_state_change(
            self.config.service_name, old_state.value, self._state.value
        )

        logger.warning(
            "circuit_breaker_opened",
            service=self.config.service_name,
            failure_count=self._failure_count,
            threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
            previous_state=old_state.value,
        )

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        old_state = self._state
        self._state = CircuitBreakerState.HALF_OPEN
        self._success_count_in_half_open = 0
        self._stats.state_transitions += 1
        self._stats.last_state_change_time = time.time()

        # Record Prometheus metric
        record_circuit_breaker_state_change(
            self.config.service_name, old_state.value, self._state.value
        )

        logger.info(
            "circuit_breaker_half_open",
            service=self.config.service_name,
            testing_recovery=True,
            previous_state=old_state.value,
        )

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        old_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count_in_half_open = 0
        self._stats.state_transitions += 1
        self._stats.last_state_change_time = time.time()

        # Record Prometheus metric
        record_circuit_breaker_state_change(
            self.config.service_name, old_state.value, self._state.value
        )

        logger.info(
            "circuit_breaker_closed",
            service=self.config.service_name,
            recovered=True,
            previous_state=old_state.value,
        )

    def get_health_status(self) -> dict[str, Any]:
        """
        Get health status for monitoring and health endpoints.

        Returns:
            Dictionary with state, stats, and configuration.
        """
        return {
            "service": self.config.service_name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.config.failure_threshold,
            "recovery_timeout": self.config.recovery_timeout,
            "recovery_time_remaining": self._get_recovery_time_remaining(),
            "stats": {
                "total_requests": self._stats.total_requests,
                "successful_requests": self._stats.successful_requests,
                "failed_requests": self._stats.failed_requests,
                "rejected_requests": self._stats.rejected_requests,
                "state_transitions": self._stats.state_transitions,
            },
        }

    def reset(self) -> None:
        """Reset circuit breaker to initial state (for testing)."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count_in_half_open = 0
        self._last_failure_time = None
        self._stats = CircuitBreakerStats()

        logger.info(
            "circuit_breaker_reset",
            service=self.config.service_name,
        )
