"""
Unit tests for Circuit Breaker Registry.

Tests cover:
- Registration and retrieval
- Idempotent registration
- Health status aggregation
- Open circuits detection
- Reset functionality
"""

import pytest

from src.core.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerState,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    CircuitBreakerRegistry.clear()
    yield
    CircuitBreakerRegistry.clear()


class TestRegistration:
    """Test circuit breaker registration."""

    def test_register_new_breaker(self):
        """Register creates new circuit breaker."""
        config = CircuitBreakerConfig(service_name="test_service")
        cb = CircuitBreakerRegistry.register(config)

        assert isinstance(cb, CircuitBreaker)
        assert cb.config.service_name == "test_service"

    def test_register_idempotent(self):
        """Registering same service returns existing breaker."""
        config1 = CircuitBreakerConfig(service_name="test_service", failure_threshold=5)
        config2 = CircuitBreakerConfig(service_name="test_service", failure_threshold=10)

        cb1 = CircuitBreakerRegistry.register(config1)
        cb2 = CircuitBreakerRegistry.register(config2)

        assert cb1 is cb2
        # Original config is kept
        assert cb1.config.failure_threshold == 5

    def test_get_existing(self):
        """Get returns existing circuit breaker."""
        config = CircuitBreakerConfig(service_name="my_service")
        registered = CircuitBreakerRegistry.register(config)

        retrieved = CircuitBreakerRegistry.get("my_service")

        assert retrieved is registered

    def test_get_nonexistent(self):
        """Get returns None for non-existent service."""
        result = CircuitBreakerRegistry.get("nonexistent")
        assert result is None

    def test_get_or_create_new(self):
        """get_or_create creates new breaker if not exists."""
        cb = CircuitBreakerRegistry.get_or_create(
            service_name="new_service",
            failure_threshold=10,
            recovery_timeout=30.0,
        )

        assert cb.config.service_name == "new_service"
        assert cb.config.failure_threshold == 10
        assert cb.config.recovery_timeout == 30.0

    def test_get_or_create_existing(self):
        """get_or_create returns existing breaker if exists."""
        config = CircuitBreakerConfig(service_name="service", failure_threshold=5)
        original = CircuitBreakerRegistry.register(config)

        cb = CircuitBreakerRegistry.get_or_create(
            service_name="service",
            failure_threshold=10,  # Different config
        )

        assert cb is original
        assert cb.config.failure_threshold == 5  # Original preserved


class TestHealthStatus:
    """Test health status aggregation."""

    def test_get_all_health_status_empty(self):
        """Returns empty dict when no breakers registered."""
        status = CircuitBreakerRegistry.get_all_health_status()
        assert status == {}

    def test_get_all_health_status(self):
        """Returns health status for all registered breakers."""
        CircuitBreakerRegistry.register(
            CircuitBreakerConfig(service_name="service_a")
        )
        CircuitBreakerRegistry.register(
            CircuitBreakerConfig(service_name="service_b")
        )

        status = CircuitBreakerRegistry.get_all_health_status()

        assert "service_a" in status
        assert "service_b" in status
        assert status["service_a"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_get_open_circuits_empty(self):
        """Returns empty list when no circuits are open."""
        CircuitBreakerRegistry.register(
            CircuitBreakerConfig(service_name="healthy_service")
        )

        open_circuits = CircuitBreakerRegistry.get_open_circuits()
        assert open_circuits == []

    @pytest.mark.asyncio
    async def test_get_open_circuits(self):
        """Returns list of services with open circuits."""
        config_a = CircuitBreakerConfig(service_name="service_a", failure_threshold=1)
        config_b = CircuitBreakerConfig(service_name="service_b", failure_threshold=1)

        cb_a = CircuitBreakerRegistry.register(config_a)
        CircuitBreakerRegistry.register(config_b)

        # Open circuit A
        await cb_a.record_failure(Exception("error"))

        open_circuits = CircuitBreakerRegistry.get_open_circuits()

        assert "service_a" in open_circuits
        assert "service_b" not in open_circuits


class TestResetFunctionality:
    """Test reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_single(self):
        """Reset resets a single circuit breaker."""
        config = CircuitBreakerConfig(service_name="service", failure_threshold=1)
        cb = CircuitBreakerRegistry.register(config)

        # Open the circuit
        await cb.record_failure(Exception("error"))
        assert cb.state == CircuitBreakerState.OPEN

        # Reset
        result = CircuitBreakerRegistry.reset("service")

        assert result is True
        assert cb.state == CircuitBreakerState.CLOSED

    def test_reset_nonexistent(self):
        """Reset returns False for non-existent service."""
        result = CircuitBreakerRegistry.reset("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_all(self):
        """reset_all resets all circuit breakers."""
        config_a = CircuitBreakerConfig(service_name="service_a", failure_threshold=1)
        config_b = CircuitBreakerConfig(service_name="service_b", failure_threshold=1)

        cb_a = CircuitBreakerRegistry.register(config_a)
        cb_b = CircuitBreakerRegistry.register(config_b)

        # Open both circuits
        await cb_a.record_failure(Exception("error"))
        await cb_b.record_failure(Exception("error"))

        # Reset all
        CircuitBreakerRegistry.reset_all()

        assert cb_a.state == CircuitBreakerState.CLOSED
        assert cb_b.state == CircuitBreakerState.CLOSED


class TestUtilityMethods:
    """Test utility methods."""

    def test_count_empty(self):
        """Count returns 0 when no breakers registered."""
        assert CircuitBreakerRegistry.count() == 0

    def test_count(self):
        """Count returns number of registered breakers."""
        CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="a"))
        CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="b"))
        CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="c"))

        assert CircuitBreakerRegistry.count() == 3

    def test_get_all(self):
        """get_all returns copy of all breakers."""
        cb_a = CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="a"))
        cb_b = CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="b"))

        all_breakers = CircuitBreakerRegistry.get_all()

        assert all_breakers["a"] is cb_a
        assert all_breakers["b"] is cb_b

        # Verify it's a copy
        all_breakers["c"] = "test"
        assert "c" not in CircuitBreakerRegistry.get_all()

    def test_clear(self):
        """clear removes all registered breakers."""
        CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="a"))
        CircuitBreakerRegistry.register(CircuitBreakerConfig(service_name="b"))

        CircuitBreakerRegistry.clear()

        assert CircuitBreakerRegistry.count() == 0
        assert CircuitBreakerRegistry.get("a") is None
