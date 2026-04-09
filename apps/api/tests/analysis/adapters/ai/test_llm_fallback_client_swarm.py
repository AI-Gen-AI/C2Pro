"""
FallbackAIClient — retry / circuit-breaker unit tests (Swarm, P1-03).

Refers to Suite ID: TS-INT-EXT-LLM-002.

Coverage:
  Retry exhaustion
    - primary succeeds on first attempt → no retries, no fallback
    - primary fails once, succeeds on second attempt → single retry used
    - primary fails all attempts → fallback used
    - retry count respected (max_retries=0 means no retry)

  Exponential backoff timing
    - delays double on each retry: base, base*2, base*4 …
    - no sleep on first attempt

  Circuit breaker state transitions
    - CLOSED → OPEN after failure_threshold consecutive failures
    - OPEN circuit fast-fails primary; fallback is used without calling primary
    - OPEN → HALF_OPEN after recovery_timeout elapses
    - HALF_OPEN → CLOSED on success
    - HALF_OPEN → OPEN on failure (re-opens immediately)
    - failure counter resets after a success in CLOSED state
    - circuit stays CLOSED while failures < threshold
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from src.analysis.adapters.ai.llm_fallback_client import (
    CircuitBreaker,
    CircuitState,
    FallbackAIClient,
)
from src.analysis.ports.ai_client import IAIClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeClient(IAIClient):
    """Configurable stub for IAIClient."""

    response: dict | None = None
    fail_times: int = 0  # raise RuntimeError for the first N calls
    calls: int = field(default=0, init=False)

    async def extract_json(self, system_prompt: str, user_content: str, task_type: str):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"forced failure #{self.calls}")
        return self.response


def _make_client(
    *,
    primary_response=None,
    primary_fail_times: int = 0,
    fallback_response=None,
    max_retries: int = 2,
    base_delay: float = 0.0,  # zero for fast tests
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
) -> tuple[FallbackAIClient, _FakeClient, _FakeClient]:
    primary = _FakeClient(response=primary_response, fail_times=primary_fail_times)
    fallback = _FakeClient(response=fallback_response)
    client = FallbackAIClient(
        primary=primary,
        fallback=fallback,
        max_retries=max_retries,
        base_delay=base_delay,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )
    return client, primary, fallback


# ---------------------------------------------------------------------------
# Retry exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.unit
class TestRetryExhaustion:
    async def test_primary_succeeds_first_attempt_no_fallback(self) -> None:
        client, primary, fallback = _make_client(
            primary_response={"ok": True},
            max_retries=2,
        )
        result = await client.extract_json("sys", "user", "risk")

        assert result == {"ok": True}
        assert primary.calls == 1
        assert fallback.calls == 0

    async def test_primary_fails_once_then_succeeds_on_retry(self) -> None:
        client, primary, fallback = _make_client(
            primary_response={"ok": True},
            primary_fail_times=1,
            max_retries=2,
        )
        result = await client.extract_json("sys", "user", "risk")

        assert result == {"ok": True}
        assert primary.calls == 2
        assert fallback.calls == 0

    async def test_all_retries_exhausted_uses_fallback(self) -> None:
        client, primary, fallback = _make_client(
            primary_fail_times=99,  # always fails
            fallback_response={"from": "fallback"},
            max_retries=2,
        )
        result = await client.extract_json("sys", "user", "risk")

        assert result == {"from": "fallback"}
        assert primary.calls == 3  # initial + 2 retries
        assert fallback.calls == 1

    async def test_max_retries_zero_means_no_retry(self) -> None:
        client, primary, fallback = _make_client(
            primary_fail_times=99,
            fallback_response={"from": "fallback"},
            max_retries=0,
        )
        result = await client.extract_json("sys", "user", "risk")

        assert result == {"from": "fallback"}
        assert primary.calls == 1  # no retry
        assert fallback.calls == 1

    async def test_fallback_result_returned_when_primary_always_fails(self) -> None:
        client, _primary, fallback = _make_client(
            primary_fail_times=99,
            fallback_response={"data": 42},
            max_retries=1,
        )
        result = await client.extract_json("s", "u", "t")

        assert result == {"data": 42}
        assert fallback.calls == 1


# ---------------------------------------------------------------------------
# Exponential backoff timing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.unit
class TestExponentialBackoff:
    async def test_no_sleep_on_first_attempt(self) -> None:
        client, _p, _f = _make_client(
            primary_response={"ok": True},
            base_delay=1.0,
            max_retries=2,
        )
        with patch("src.analysis.adapters.ai.llm_fallback_client.asyncio.sleep") as mock_sleep:
            await client.extract_json("s", "u", "t")
            mock_sleep.assert_not_called()

    async def test_backoff_doubles_each_retry(self) -> None:
        """Verify delays: base*1, base*2 on retry 1 and retry 2."""
        client, _p, _f = _make_client(
            primary_fail_times=99,
            fallback_response=None,
            base_delay=1.0,
            max_retries=3,
        )
        sleep_calls: list[float] = []

        async def _fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("src.analysis.adapters.ai.llm_fallback_client.asyncio.sleep", side_effect=_fake_sleep):
            await client.extract_json("s", "u", "t")

        assert sleep_calls == [1.0, 2.0, 4.0]  # base*(2^0), base*(2^1), base*(2^2)

    async def test_single_retry_uses_base_delay(self) -> None:
        client, _p, _f = _make_client(
            primary_fail_times=99,
            fallback_response=None,
            base_delay=0.5,
            max_retries=1,
        )
        sleep_calls: list[float] = []

        async def _fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("src.analysis.adapters.ai.llm_fallback_client.asyncio.sleep", side_effect=_fake_sleep):
            await client.extract_json("s", "u", "t")

        assert sleep_calls == [0.5]


# ---------------------------------------------------------------------------
# Circuit breaker states
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCircuitBreakerUnit:
    """Pure unit tests for CircuitBreaker state machine (synchronous)."""

    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        assert cb.state is CircuitState.CLOSED

    def test_failures_below_threshold_stay_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state is CircuitState.CLOSED

    def test_failures_at_threshold_opens_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state is CircuitState.OPEN

    def test_success_resets_failure_counter_and_closes(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # Failure counter reset; two more failures should NOT open yet.
        cb.record_failure()
        cb.record_failure()
        assert cb.state is CircuitState.CLOSED

    def test_open_circuit_is_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()

    def test_half_open_after_recovery_timeout(self, monkeypatch) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        cb.record_failure()
        assert cb.state is CircuitState.OPEN

        # Simulate time passing beyond recovery_timeout.
        monkeypatch.setattr(
            "src.analysis.adapters.ai.llm_fallback_client.time.monotonic",
            lambda: cb._opened_at + 10.1,  # type: ignore[operator]
        )
        assert cb.state is CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self, monkeypatch) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        cb.record_failure()
        monkeypatch.setattr(
            "src.analysis.adapters.ai.llm_fallback_client.time.monotonic",
            lambda: cb._opened_at + 10.1,  # type: ignore[operator]
        )
        assert cb.state is CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state is CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self, monkeypatch) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        cb.record_failure()
        opened_at = cb._opened_at  # capture before patch so lambda is stable
        monkeypatch.setattr(
            "src.analysis.adapters.ai.llm_fallback_client.time.monotonic",
            lambda: opened_at + 10.1,  # type: ignore[operator]
        )
        assert cb.state is CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state is CircuitState.OPEN

    def test_open_not_yet_recovered_stays_open(self, monkeypatch) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        cb.record_failure()
        monkeypatch.setattr(
            "src.analysis.adapters.ai.llm_fallback_client.time.monotonic",
            lambda: cb._opened_at + 5.0,  # type: ignore[operator]
        )
        assert cb.state is CircuitState.OPEN


# ---------------------------------------------------------------------------
# Circuit breaker integration with FallbackAIClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.unit
class TestCircuitBreakerIntegration:
    async def test_open_circuit_skips_primary_uses_fallback(self) -> None:
        """When the circuit is already OPEN the primary must NOT be called."""
        client, primary, fallback = _make_client(
            primary_fail_times=99,
            fallback_response={"src": "fallback"},
            max_retries=0,
            failure_threshold=1,
        )
        # Trip the circuit by forcing a failure.
        await client.extract_json("s", "u", "t")
        primary.calls = 0  # reset call counter

        # Circuit is now OPEN; next call should bypass primary entirely.
        result = await client.extract_json("s", "u", "t")

        assert result == {"src": "fallback"}
        assert primary.calls == 0
        assert fallback.calls == 2

    async def test_circuit_opens_after_threshold_failures(self) -> None:
        client, primary, fallback = _make_client(
            primary_fail_times=99,
            fallback_response=None,
            max_retries=0,
            failure_threshold=3,
        )
        for _ in range(3):
            await client.extract_json("s", "u", "t")

        assert client.circuit.state is CircuitState.OPEN

    async def test_circuit_closed_while_primary_succeeds(self) -> None:
        client, _p, _f = _make_client(
            primary_response={"ok": True},
            max_retries=0,
            failure_threshold=2,
        )
        for _ in range(5):
            await client.extract_json("s", "u", "t")

        assert client.circuit.state is CircuitState.CLOSED

    async def test_circuit_recovers_and_closes_on_success(self, monkeypatch) -> None:
        """
        Sequence:
          1. Trip circuit OPEN (failure_threshold=1).
          2. Advance clock beyond recovery_timeout → HALF_OPEN.
          3. Primary succeeds → circuit closes.
        """
        client, primary, fallback = _make_client(
            primary_fail_times=1,   # fails once to trip circuit
            primary_response={"ok": True},
            fallback_response={"src": "fallback"},
            max_retries=0,
            failure_threshold=1,
            recovery_timeout=10.0,
        )
        # Trip circuit.
        await client.extract_json("s", "u", "t")
        assert client.circuit.state is CircuitState.OPEN

        # Advance time.
        opened_at = client.circuit._opened_at
        monkeypatch.setattr(
            "src.analysis.adapters.ai.llm_fallback_client.time.monotonic",
            lambda: opened_at + 10.1,
        )
        assert client.circuit.state is CircuitState.HALF_OPEN

        # Primary now succeeds → circuit should close.
        result = await client.extract_json("s", "u", "t")
        assert result == {"ok": True}
        assert client.circuit.state is CircuitState.CLOSED

    async def test_circuit_stays_open_on_half_open_failure(self, monkeypatch) -> None:
        """HALF_OPEN → failure → back to OPEN."""
        client, primary, fallback = _make_client(
            primary_fail_times=99,   # always fails
            fallback_response={"src": "fallback"},
            max_retries=0,
            failure_threshold=1,
            recovery_timeout=10.0,
        )
        # Trip circuit.
        await client.extract_json("s", "u", "t")
        opened_at = client.circuit._opened_at

        # Advance time to HALF_OPEN.
        monkeypatch.setattr(
            "src.analysis.adapters.ai.llm_fallback_client.time.monotonic",
            lambda: opened_at + 10.1,
        )
        assert client.circuit.state is CircuitState.HALF_OPEN

        # Primary fails again in HALF_OPEN → back to OPEN.
        await client.extract_json("s", "u", "t")
        assert client.circuit.state is CircuitState.OPEN
