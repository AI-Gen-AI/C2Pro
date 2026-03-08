"""
Unit tests for Circuit Breaker implementation.

Tests cover:
- State transitions (closed -> open -> half_open -> closed)
- Failure counting and thresholds
- Recovery timeout behavior
- Excluded exceptions
- Async and sync methods
- Statistics tracking
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from src.core.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)


class TestCircuitBreakerState:
    """Test circuit breaker state transitions."""

    @pytest.fixture
    def cb(self):
        """Create a circuit breaker with low thresholds for testing."""
        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=3,
            recovery_timeout=1.0,
            success_threshold_in_half_open=2,
        )
        return CircuitBreaker(config)

    @pytest.mark.asyncio
    async def test_starts_closed(self, cb):
        """Circuit breaker starts in closed state."""
        assert cb.state == CircuitBreakerState.CLOSED
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, cb):
        """Circuit opens after reaching failure threshold."""
        # Record failures below threshold
        await cb.record_failure(Exception("error 1"))
        assert cb.state == CircuitBreakerState.CLOSED

        await cb.record_failure(Exception("error 2"))
        assert cb.state == CircuitBreakerState.CLOSED

        # Third failure should open the circuit
        await cb.record_failure(Exception("error 3"))
        assert cb.state == CircuitBreakerState.OPEN
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_half_opens_after_recovery_timeout(self, cb):
        """Circuit transitions to half-open after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            await cb.record_failure(Exception("error"))

        assert cb.state == CircuitBreakerState.OPEN
        assert await cb.can_execute() is False

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Should transition to half-open on next check
        assert await cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self, cb):
        """Circuit closes after successful requests in half-open state."""
        # Open the circuit
        for _ in range(3):
            await cb.record_failure(Exception("error"))

        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        await cb.can_execute()  # Triggers transition to half-open
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # First success
        await cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Second success should close the circuit
        await cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self, cb):
        """Circuit reopens on failure in half-open state."""
        # Open the circuit
        for _ in range(3):
            await cb.record_failure(Exception("error"))

        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        await cb.can_execute()  # Triggers transition to half-open
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Any failure in half-open reopens the circuit
        await cb.record_failure(Exception("error"))
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_success_decays_failure_count_in_closed(self, cb):
        """Success in closed state decays failure count."""
        await cb.record_failure(Exception("error 1"))
        await cb.record_failure(Exception("error 2"))
        assert cb.failure_count == 2

        # Success should decay failure count
        await cb.record_success()
        assert cb.failure_count == 1

        await cb.record_success()
        assert cb.failure_count == 0


class TestExcludedExceptions:
    """Test excluded exceptions behavior."""

    @pytest.mark.asyncio
    async def test_excluded_exceptions_dont_trip_circuit(self):
        """Excluded exceptions don't contribute to failure count."""

        class ValidationError(Exception):
            pass

        class AuthError(Exception):
            pass

        config = CircuitBreakerConfig(
            service_name="test_service",
            failure_threshold=2,
            recovery_timeout=60.0,
            excluded_exceptions=(ValidationError, AuthError),
        )
        cb = CircuitBreaker(config)

        # Excluded exceptions don't count
        await cb.record_failure(ValidationError("invalid"))
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

        await cb.record_failure(AuthError("unauthorized"))
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

        # Non-excluded exceptions do count
        await cb.record_failure(Exception("server error"))
        assert cb.failure_count == 1

        await cb.record_failure(RuntimeError("timeout"))
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN


class TestSyncMethods:
    """Test synchronous methods for non-async contexts."""

    def test_can_execute_sync_closed(self):
        """can_execute_sync works in closed state."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=3)
        cb = CircuitBreaker(config)

        assert cb.can_execute_sync() is True

    def test_record_success_sync(self):
        """record_success_sync works correctly."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=3)
        cb = CircuitBreaker(config)

        # Record some failures
        cb.record_failure_sync(Exception("error"))
        cb.record_failure_sync(Exception("error"))
        assert cb.failure_count == 2

        # Success should decay count
        cb.record_success_sync()
        assert cb.failure_count == 1

    def test_record_failure_sync_opens_circuit(self):
        """record_failure_sync opens circuit at threshold."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=2)
        cb = CircuitBreaker(config)

        cb.record_failure_sync(Exception("error 1"))
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure_sync(Exception("error 2"))
        assert cb.state == CircuitBreakerState.OPEN


class TestCallMethod:
    """Test the call() wrapper method."""

    @pytest.mark.asyncio
    async def test_call_success(self):
        """call() records success on successful function execution."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=3)
        cb = CircuitBreaker(config)

        async def success_func():
            return "result"

        result = await cb.call(success_func)
        assert result == "result"
        assert cb._stats.successful_requests == 1

    @pytest.mark.asyncio
    async def test_call_failure(self):
        """call() records failure on exception."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=3)
        cb = CircuitBreaker(config)

        async def fail_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await cb.call(fail_func)

        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_call_raises_when_open(self):
        """call() raises CircuitBreakerOpenError when circuit is open."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=1)
        cb = CircuitBreaker(config)

        # Open the circuit
        await cb.record_failure(Exception("error"))
        assert cb.state == CircuitBreakerState.OPEN

        async def func():
            return "result"

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await cb.call(func)

        assert exc_info.value.service_name == "test"


class TestStatistics:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_tracks_request_counts(self):
        """Statistics track all request types."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=3)
        cb = CircuitBreaker(config)

        # Successes
        await cb.record_success()
        await cb.record_success()

        # Failures
        await cb.record_failure(Exception("error"))

        stats = cb.get_health_status()["stats"]
        assert stats["total_requests"] == 3
        assert stats["successful_requests"] == 2
        assert stats["failed_requests"] == 1

    @pytest.mark.asyncio
    async def test_tracks_rejections(self):
        """Statistics track rejected requests."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=1)
        cb = CircuitBreaker(config)

        # Open the circuit
        await cb.record_failure(Exception("error"))

        # Record rejections
        await cb.record_rejection()
        await cb.record_rejection()

        stats = cb.get_health_status()["stats"]
        assert stats["rejected_requests"] == 2

    @pytest.mark.asyncio
    async def test_tracks_state_transitions(self):
        """Statistics track state transitions."""
        config = CircuitBreakerConfig(
            service_name="test",
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold_in_half_open=1,
        )
        cb = CircuitBreaker(config)

        # closed -> open
        await cb.record_failure(Exception("error"))

        # Wait for recovery
        await asyncio.sleep(0.2)

        # open -> half_open
        await cb.can_execute()

        # half_open -> closed
        await cb.record_success()

        stats = cb.get_health_status()["stats"]
        assert stats["state_transitions"] == 3


class TestHealthStatus:
    """Test get_health_status() method."""

    @pytest.mark.asyncio
    async def test_returns_complete_status(self):
        """Health status includes all relevant information."""
        config = CircuitBreakerConfig(
            service_name="my_service",
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        cb = CircuitBreaker(config)

        status = cb.get_health_status()

        assert status["service"] == "my_service"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 5
        assert status["recovery_timeout"] == 60.0
        assert status["recovery_time_remaining"] is None
        assert "stats" in status

    @pytest.mark.asyncio
    async def test_shows_recovery_time_remaining(self):
        """Health status shows recovery time when circuit is open."""
        config = CircuitBreakerConfig(
            service_name="test",
            failure_threshold=1,
            recovery_timeout=60.0,
        )
        cb = CircuitBreaker(config)

        # Open the circuit
        await cb.record_failure(Exception("error"))

        status = cb.get_health_status()
        assert status["state"] == "open"
        assert status["recovery_time_remaining"] is not None
        assert status["recovery_time_remaining"] > 0


class TestReset:
    """Test reset() method."""

    @pytest.mark.asyncio
    async def test_reset_returns_to_initial_state(self):
        """reset() returns circuit breaker to initial state."""
        config = CircuitBreakerConfig(service_name="test", failure_threshold=1)
        cb = CircuitBreaker(config)

        # Open the circuit
        await cb.record_failure(Exception("error"))
        await cb.record_rejection()
        assert cb.state == CircuitBreakerState.OPEN

        # Reset
        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb._stats.total_requests == 0
        assert cb._stats.rejected_requests == 0


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_failure_threshold(self):
        """Raises error for invalid failure threshold."""
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreakerConfig(service_name="test", failure_threshold=0)

    def test_invalid_recovery_timeout(self):
        """Raises error for invalid recovery timeout."""
        with pytest.raises(ValueError, match="recovery_timeout"):
            CircuitBreakerConfig(service_name="test", recovery_timeout=0)

    def test_invalid_success_threshold(self):
        """Raises error for invalid success threshold."""
        with pytest.raises(ValueError, match="success_threshold_in_half_open"):
            CircuitBreakerConfig(service_name="test", success_threshold_in_half_open=0)
