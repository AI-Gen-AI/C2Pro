"""Circuit breaker decorator unit coverage.

Test Suite ID: TASK-OPS-DOCFLOW-013
"""

from types import SimpleNamespace

import pytest

from src.core.resilience import decorators
from src.core.resilience.circuit_breaker import CircuitBreakerOpenError


class _AsyncCircuitBreaker:
    def __init__(self, *, can_execute: bool) -> None:
        self.can_execute_result = can_execute
        self.rejections = 0
        self.successes = 0
        self.failures: list[Exception] = []

    async def can_execute(self) -> bool:
        return self.can_execute_result

    async def record_rejection(self) -> None:
        self.rejections += 1

    async def record_success(self) -> None:
        self.successes += 1

    async def record_failure(self, exc: Exception) -> None:
        self.failures.append(exc)

    def _get_recovery_time_remaining(self) -> float:
        return 7.0


class _SyncCircuitBreaker:
    def __init__(self, *, can_execute: bool) -> None:
        self.can_execute_result = can_execute
        self.successes = 0
        self.failures: list[Exception] = []

    def can_execute_sync(self) -> bool:
        return self.can_execute_result

    def record_success_sync(self) -> None:
        self.successes += 1

    def record_failure_sync(self, exc: Exception) -> None:
        self.failures.append(exc)

    def _get_recovery_time_remaining(self) -> float:
        return 9.0


def _enable_circuit_breakers(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    monkeypatch.setattr(
        decorators,
        "get_circuit_breaker_settings",
        lambda: SimpleNamespace(enable_circuit_breakers=enabled),
    )


@pytest.mark.asyncio
async def test_async_decorator_bypasses_registry_when_disabled(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: disabled async decorators call the function directly."""
    _enable_circuit_breakers(monkeypatch, False)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: pytest.fail("registry should not be used when disabled"),
    )

    @decorators.with_circuit_breaker("payments")
    async def fetch_value() -> str:
        return "direct"

    assert await fetch_value() == "direct"


@pytest.mark.asyncio
async def test_async_decorator_records_success_and_uses_custom_thresholds(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: async decorators create breakers and record success."""
    _enable_circuit_breakers(monkeypatch, True)
    breaker = _AsyncCircuitBreaker(can_execute=True)
    calls: list[dict[str, object]] = []

    def get_or_create(**kwargs: object) -> _AsyncCircuitBreaker:
        calls.append(kwargs)
        return breaker

    monkeypatch.setattr(decorators.CircuitBreakerRegistry, "get_or_create", get_or_create)

    @decorators.with_circuit_breaker("search", failure_threshold=2, recovery_timeout=3.0)
    async def fetch_value() -> str:
        return "ok"

    assert await fetch_value() == "ok"
    assert breaker.successes == 1
    assert calls == [
        {
            "service_name": "search",
            "failure_threshold": 2,
            "recovery_timeout": 3.0,
        }
    ]


@pytest.mark.asyncio
async def test_async_decorator_uses_fallback_when_open(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: open async circuits record rejection and call fallback."""
    _enable_circuit_breakers(monkeypatch, True)
    breaker = _AsyncCircuitBreaker(can_execute=False)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: breaker,
    )

    @decorators.with_circuit_breaker("search", fallback=lambda: "degraded")
    async def fetch_value() -> str:
        return "unreachable"

    assert await fetch_value() == "degraded"
    assert breaker.rejections == 1


@pytest.mark.asyncio
async def test_async_decorator_raises_when_open_without_fallback(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: open async circuits raise without a fallback."""
    _enable_circuit_breakers(monkeypatch, True)
    breaker = _AsyncCircuitBreaker(can_execute=False)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: breaker,
    )

    @decorators.with_circuit_breaker("search")
    async def fetch_value() -> str:
        return "unreachable"

    with pytest.raises(CircuitBreakerOpenError, match="search"):
        await fetch_value()


@pytest.mark.asyncio
async def test_async_decorator_records_failure_and_can_return_exception_fallback(
    monkeypatch,
) -> None:
    """TASK-OPS-DOCFLOW-013: async decorator fallback can replace failures."""
    _enable_circuit_breakers(monkeypatch, True)
    breaker = _AsyncCircuitBreaker(can_execute=True)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: breaker,
    )

    @decorators.with_circuit_breaker("search", fallback=lambda: "fallback", reraise=False)
    async def fetch_value() -> str:
        raise RuntimeError("boom")

    assert await fetch_value() == "fallback"
    assert [type(exc) for exc in breaker.failures] == [RuntimeError]


def test_sync_decorator_bypasses_registry_when_disabled(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: disabled sync decorators call the function directly."""
    _enable_circuit_breakers(monkeypatch, False)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: pytest.fail("registry should not be used when disabled"),
    )

    @decorators.with_circuit_breaker_sync("cache")
    def fetch_value() -> str:
        return "direct"

    assert fetch_value() == "direct"


def test_sync_decorator_records_success_and_open_fallback(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: sync decorators record success and handle open fallback."""
    _enable_circuit_breakers(monkeypatch, True)
    success_breaker = _SyncCircuitBreaker(can_execute=True)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: success_breaker,
    )

    @decorators.with_circuit_breaker_sync("cache")
    def fetch_value() -> str:
        return "ok"

    assert fetch_value() == "ok"
    assert success_breaker.successes == 1

    open_breaker = _SyncCircuitBreaker(can_execute=False)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: open_breaker,
    )

    @decorators.with_circuit_breaker_sync("cache", fallback=lambda: "cached")
    def fetch_fallback() -> str:
        return "unreachable"

    assert fetch_fallback() == "cached"


def test_sync_decorator_records_failure_and_can_return_exception_fallback(
    monkeypatch,
) -> None:
    """TASK-OPS-DOCFLOW-013: sync decorator fallback can replace failures."""
    _enable_circuit_breakers(monkeypatch, True)
    breaker = _SyncCircuitBreaker(can_execute=True)
    monkeypatch.setattr(
        decorators.CircuitBreakerRegistry,
        "get_or_create",
        lambda **_: breaker,
    )

    @decorators.with_circuit_breaker_sync("cache", fallback=lambda: "fallback", reraise=False)
    def fetch_value() -> str:
        raise RuntimeError("boom")

    assert fetch_value() == "fallback"
    assert [type(exc) for exc in breaker.failures] == [RuntimeError]
