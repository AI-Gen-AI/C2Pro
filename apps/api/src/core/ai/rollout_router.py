"""TS-AI-LANGSMITH-032: Deterministic canary router for traced AI execution paths."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar
from uuid import UUID

T = TypeVar("T")


@dataclass(frozen=True)
class LangSmithRolloutConfig:
    """TS-AI-LANGSMITH-032: Runtime rollout controls for trace canary routing."""

    rollout_percentage: int
    fail_open_enabled: bool

    @classmethod
    def from_env(cls) -> "LangSmithRolloutConfig":
        rollout_raw = os.getenv("LANGSMITH_ROLLOUT_PERCENTAGE", "0").strip()
        fail_open_raw = os.getenv("LANGSMITH_ROLLOUT_FAIL_OPEN", "true").strip().lower()

        try:
            rollout_percentage = int(rollout_raw)
        except ValueError as exc:  # pragma: no cover - env guard
            raise ValueError("LANGSMITH_ROLLOUT_PERCENTAGE must be an integer") from exc

        if rollout_percentage < 0 or rollout_percentage > 100:
            raise ValueError("LANGSMITH_ROLLOUT_PERCENTAGE must be between 0 and 100")

        return cls(
            rollout_percentage=rollout_percentage,
            fail_open_enabled=fail_open_raw in {"1", "true", "yes", "on"},
        )


def should_trace_request(tenant_id: UUID | str, rollout_percentage: int) -> bool:
    """TS-AI-LANGSMITH-032: Deterministically route tenants into the canary cohort."""
    if rollout_percentage <= 0:
        return False
    if rollout_percentage >= 100:
        return True

    stable_key = str(tenant_id).strip().lower().encode("utf-8")
    hash_value = int(hashlib.md5(stable_key).hexdigest(), 16)
    return (hash_value % 100) < rollout_percentage


class LangSmithCanaryRouter:
    """TS-AI-LANGSMITH-032: Route traced/legacy execution with resilient fail-open fallback."""

    def __init__(self, config: LangSmithRolloutConfig | None = None) -> None:
        self.config = config or LangSmithRolloutConfig.from_env()

    async def route(
        self,
        *,
        tenant_id: UUID | str,
        traced_call: Callable[[], Awaitable[T]],
        legacy_call: Callable[[], Awaitable[T]],
    ) -> T:
        should_trace = should_trace_request(tenant_id, self.config.rollout_percentage)
        if not should_trace:
            return await legacy_call()

        try:
            return await traced_call()
        except Exception:
            if self.config.fail_open_enabled:
                return await legacy_call()
            raise
