"""Per-run limits and the call budget of the WBS Reviewer (ADR-030 §A16; conservative v1 values).

Every model call is admitted by the budget BEFORE it starts: the call count, the per-call input
estimate, the total token budget, the cost budget (estimated with the declared maximum output) and
the elapsed time. The calls the run still owes (the REDUCE) keep their worst-case token and cost
budget reserved while MAP calls are admitted. A retry is a call. A call that fails is charged its
admitted estimate (a provider may bill a failed call). A response whose reported usage exceeds the
declared per-call limits is discarded (OVER_LIMIT) and still charged. Once a cap is reached, or the
run is cancelled, no further call begins. Every cap has a hard ceiling.

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
MAX_TOTAL_TOKENS_CEILING: Final = 1_000_000
MAX_COST_MICRO_USD_CEILING: Final = 5_000_000
MAX_ELAPSED_MS_CEILING: Final = 1_800_000
CHARS_PER_TOKEN: Final = 4  # the admission estimate (characters per token)
EVIDENCE_SHARE: Final = 0.45  # of a call's input budget: the evidence every call carries
EXCERPT_OVERHEAD_CHARS: Final = 120  # isolation markers around one excerpt
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
    max_total_tokens: int = 600_000  # coherent with 24 calls of bounded input and maximum output
    max_cost_micro_usd: int = 3_000_000
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
        ceilings = {"max_total_tokens": MAX_TOTAL_TOKENS_CEILING, "max_cost_micro_usd": MAX_COST_MICRO_USD_CEILING,
                    "max_elapsed_ms": MAX_ELAPSED_MS_CEILING}
        for name, ceiling in ceilings.items():
            if getattr(self, name) > ceiling:
                raise ValueError(f"{name} is at most {ceiling}")
        if self.input_micro_usd_per_1k < 1 or self.output_micro_usd_per_1k < 1:
            raise ValueError("estimation rates are positive (a zero rate would disable the cost cap)")

    @property
    def evidence_chars(self) -> int:
        """Characters of evidence (with markers) one call may carry: the manifest never exceeds it."""
        return int(self.max_input_tokens_per_call * CHARS_PER_TOKEN * EVIDENCE_SHARE)

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> int:
        return math.ceil(input_tokens * self.input_micro_usd_per_1k / 1000) + math.ceil(
            output_tokens * self.output_micro_usd_per_1k / 1000)


def execution_config_digest(limits: ReviewLimits) -> str:
    """The canonical digest of every result-affecting Reviewer limit (integers only, versioned)."""
    body = {"version": EXECUTION_CONFIG_VERSION, "limits": asdict(limits)}
    return "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()


def estimate_tokens(*texts: str) -> int:
    return math.ceil(sum(len(t) for t in texts) / CHARS_PER_TOKEN)


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

    @property
    def remaining_ms(self) -> int:
        return max(0, self.limits.max_elapsed_ms - self.elapsed_ms)

    def admit(self, estimated_input_tokens: int, *, reserve_calls: int = 0) -> StopReason | None:
        """Why a call estimated at ``estimated_input_tokens`` may NOT start now (None = admitted).

        ``reserve_calls`` later calls keep their worst case (maximum input and output) reserved.
        """
        limits = self.limits
        if self.calls + 1 + reserve_calls > limits.max_calls:
            return StopReason.CALL_CAP
        reserved_tokens = reserve_calls * (limits.max_input_tokens_per_call + limits.max_output_tokens_per_call)
        if (self.input_tokens + self.output_tokens + estimated_input_tokens + limits.max_output_tokens_per_call
                + reserved_tokens > limits.max_total_tokens):
            return StopReason.TOKEN_CAP
        reserved_cost = reserve_calls * limits.estimated_cost(limits.max_input_tokens_per_call,
                                                              limits.max_output_tokens_per_call)
        if (self.cost_micro_usd + limits.estimated_cost(estimated_input_tokens, limits.max_output_tokens_per_call)
                + reserved_cost > limits.max_cost_micro_usd):
            return StopReason.COST_CAP
        if self.elapsed_ms >= limits.max_elapsed_ms:
            return StopReason.TIME_CAP
        return None

    def charge_failed(self, estimated_input_tokens: int) -> None:
        """Charge a call that started but returned no usable usage: its admitted worst case."""
        limits = self.limits
        self.input_tokens += estimated_input_tokens
        self.output_tokens += limits.max_output_tokens_per_call
        self.cost_micro_usd += limits.estimated_cost(estimated_input_tokens, limits.max_output_tokens_per_call)

    def charge(self, usage: ModelUsage) -> bool:
        """Account a response; False when it broke the declared per-call limits (discard it)."""
        self.input_tokens += max(0, usage.input_tokens)
        self.output_tokens += max(0, usage.output_tokens)
        self.cost_micro_usd += max(0, usage.cost_micro_usd)
        return (usage.input_tokens <= self.limits.max_input_tokens_per_call
                and usage.output_tokens <= self.limits.max_output_tokens_per_call)


__all__ = [
    "CHARS_PER_TOKEN",
    "EVIDENCE_SHARE",
    "EXCERPT_OVERHEAD_CHARS",
    "EXECUTION_CONFIG_VERSION",
    "MAX_CALLS_CEILING",
    "MAX_COST_MICRO_USD_CEILING",
    "MAX_ELAPSED_MS_CEILING",
    "MAX_RETRIES_CEILING",
    "MAX_TOTAL_TOKENS_CEILING",
    "CallBudget",
    "ReviewLimits",
    "StopReason",
    "estimate_tokens",
    "execution_config_digest",
]
