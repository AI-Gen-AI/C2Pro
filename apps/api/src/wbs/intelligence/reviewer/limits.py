"""Per-run limits and the call budget of the WBS Reviewer (ADR-030 §A16; conservative v1 values).

Every model call is admitted by the budget BEFORE it starts: the call count, the per-call input
estimate, the total token budget, the cost budget (estimated with the declared maximum output) and
the elapsed time. A retry is a call. A response whose reported usage exceeds the declared per-call
limits is discarded (OVER_LIMIT) and still charged. Once a cap is reached, or the run is cancelled,
no further call begins.

The execution configuration (every field below: each one changes which evidence is read, which
calls may start or which responses are kept) has a canonical, versioned digest. It binds the run's
idempotency identity, so a review under different limits is a new run, never a reused one.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Final

from src.wbs.domain.digest import canonical_json
from src.wbs.intelligence.reviewer.model_port import ModelUsage

MAX_CALLS_CEILING: Final = 24
MAX_RETRIES_CEILING: Final = 2
EXECUTION_CONFIG_VERSION: Final = "wbs-reviewer-execution-config/v1"


class StopReason(StrEnum):
    CALL_CAP = "CALL_CAP"
    TOKEN_CAP = "TOKEN_CAP"
    COST_CAP = "COST_CAP"
    TIME_CAP = "TIME_CAP"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ReviewLimits:
    """Conservative v1 limits. ``max_calls`` counts every attempt (retries included)."""

    max_calls: int = MAX_CALLS_CEILING
    max_retries: int = MAX_RETRIES_CEILING
    max_input_tokens_per_call: int = 24_000
    max_output_tokens_per_call: int = 4_000
    max_total_tokens: int = 200_000
    max_cost_micro_usd: int = 2_000_000
    # synthetic estimation rates (micro-USD per 1k tokens) used for admission only
    input_micro_usd_per_1k: int = 3_000
    output_micro_usd_per_1k: int = 15_000
    max_elapsed_ms: int = 600_000
    max_excerpts: int = 40
    max_excerpts_per_document: int = 8
    max_excerpt_chars: int = 2_000
    max_user_context_chars: int = 2_000
    max_cluster_nodes: int = 60

    def __post_init__(self) -> None:
        if not 2 <= self.max_calls <= MAX_CALLS_CEILING:
            raise ValueError(f"max_calls is between 2 (one MAP, one REDUCE) and {MAX_CALLS_CEILING}")
        if not 0 <= self.max_retries <= MAX_RETRIES_CEILING:
            raise ValueError(f"max_retries is between 0 and {MAX_RETRIES_CEILING}")
        positive = ("max_input_tokens_per_call", "max_output_tokens_per_call", "max_total_tokens",
                    "max_cost_micro_usd", "max_elapsed_ms", "max_excerpts", "max_excerpts_per_document",
                    "max_excerpt_chars", "max_user_context_chars", "max_cluster_nodes")
        for name in positive:
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if self.input_micro_usd_per_1k < 0 or self.output_micro_usd_per_1k < 0:
            raise ValueError("estimation rates are not negative")

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> int:
        return math.ceil(input_tokens * self.input_micro_usd_per_1k / 1000) + math.ceil(
            output_tokens * self.output_micro_usd_per_1k / 1000)


def execution_config_digest(limits: ReviewLimits) -> str:
    """The canonical digest of every result-affecting Reviewer limit (integers only, versioned)."""
    body = {"version": EXECUTION_CONFIG_VERSION, "limits": asdict(limits)}
    return "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()


def estimate_tokens(*texts: str) -> int:
    return math.ceil(sum(len(t) for t in texts) / 4)


@dataclass
class CallBudget:
    limits: ReviewLimits
    clock: Callable[[], float]  # seconds (monotonic)
    started: float = field(init=False)
    calls: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0

    def __post_init__(self) -> None:
        self.started = self.clock()

    @property
    def elapsed_ms(self) -> int:
        return max(0, int((self.clock() - self.started) * 1000))

    def admit(self, estimated_input_tokens: int, *, reserve_calls: int = 0) -> StopReason | None:
        """Why a call estimated at ``estimated_input_tokens`` may NOT start now (None = admitted)."""
        limits = self.limits
        if self.calls + 1 + reserve_calls > limits.max_calls:
            return StopReason.CALL_CAP
        if (self.input_tokens + self.output_tokens + estimated_input_tokens + limits.max_output_tokens_per_call
                > limits.max_total_tokens):
            return StopReason.TOKEN_CAP
        if (self.cost_micro_usd + limits.estimated_cost(estimated_input_tokens, limits.max_output_tokens_per_call)
                > limits.max_cost_micro_usd):
            return StopReason.COST_CAP
        if self.elapsed_ms > limits.max_elapsed_ms:
            return StopReason.TIME_CAP
        return None

    def charge(self, usage: ModelUsage) -> bool:
        """Account a response; False when it broke the declared per-call limits (discard it)."""
        self.input_tokens += max(0, usage.input_tokens)
        self.output_tokens += max(0, usage.output_tokens)
        self.cost_micro_usd += max(0, usage.cost_micro_usd)
        return (usage.input_tokens <= self.limits.max_input_tokens_per_call
                and usage.output_tokens <= self.limits.max_output_tokens_per_call)


__all__ = [
    "EXECUTION_CONFIG_VERSION",
    "MAX_CALLS_CEILING",
    "MAX_RETRIES_CEILING",
    "CallBudget",
    "ReviewLimits",
    "StopReason",
    "estimate_tokens",
    "execution_config_digest",
]
