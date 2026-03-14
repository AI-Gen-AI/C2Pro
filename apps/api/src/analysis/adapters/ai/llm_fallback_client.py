"""
Fallback AI client adapter with retry and circuit-breaker.

Refers to Suite ID: TS-INT-EXT-LLM-002.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any

from src.analysis.ports.ai_client import IAIClient


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Simple circuit breaker.

    Transitions:
      CLOSED  → OPEN       after ``failure_threshold`` consecutive failures
      OPEN    → HALF_OPEN  after ``recovery_timeout`` seconds
      HALF_OPEN → CLOSED   on first success
      HALF_OPEN → OPEN     on first failure
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state is CircuitState.HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def is_open(self) -> bool:
        return self.state is CircuitState.OPEN


class FallbackAIClient(IAIClient):
    """
    Attempt primary AI client with retry + circuit breaker; fall back to
    secondary on exhaustion or open circuit.

    Args:
        primary:            Primary ``IAIClient`` implementation.
        fallback:           Fallback ``IAIClient`` implementation.
        max_retries:        Number of retry attempts for the primary (0 = no retry).
        base_delay:         Base delay in seconds for exponential backoff.
        failure_threshold:  Consecutive failures before circuit opens.
        recovery_timeout:   Seconds before a OPEN circuit moves to HALF_OPEN.
    """

    def __init__(
        self,
        *,
        primary: IAIClient,
        fallback: IAIClient,
        max_retries: int = 2,
        base_delay: float = 0.5,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._circuit = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    @property
    def circuit(self) -> CircuitBreaker:
        return self._circuit

    async def extract_json(self, system_prompt: str, user_content: str, task_type: str) -> Any:
        if not self._circuit.is_open():
            last_exc: Exception | None = None
            for attempt in range(self.max_retries + 1):
                if attempt > 0:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                try:
                    result = await self._primary.extract_json(system_prompt, user_content, task_type)
                    self._circuit.record_success()
                    return result
                except Exception as exc:
                    self._circuit.record_failure()
                    last_exc = exc  # noqa: F841 — kept for potential future logging

        return await self._fallback.extract_json(system_prompt, user_content, task_type)
