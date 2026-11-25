"""Candidate-only A5 retry escrow; no environment or runtime activation."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class N4RetryPolicy:
    """Explicit opt-in to the single version authorized for local evaluation."""

    version: str = "a5-retry-escrow-v1"

    def __post_init__(self) -> None:
        if self.version != "a5-retry-escrow-v1":
            raise ValueError("Unsupported N4 retry policy")

    @property
    def initial_usd(self) -> Decimal:
        return Decimal("0.30")

    @property
    def retry_usd(self) -> Decimal:
        return Decimal("0.40")

    @property
    def run_usd(self) -> Decimal:
        return Decimal("6")

    @property
    def max_attempts(self) -> int:
        return 3

    def ceiling(self, attempt: int) -> Decimal:
        if type(attempt) is not int or not 1 <= attempt <= self.max_attempts:
            raise ValueError("N4 attempt outside A13 limit")
        return self.initial_usd if attempt == 1 else self.retry_usd

    def identity(self) -> dict:
        return {
            "version": self.version,
            "initial_usd": str(self.initial_usd),
            "retry_usd": str(self.retry_usd),
            "run_usd": str(self.run_usd),
            "max_attempts": self.max_attempts,
            "initial_tokens": 8192,
            "retry_tokens": 16384,
            "timeout_seconds": 300,
            "automatic_retries": 0,
            "fallback": False,
        }
