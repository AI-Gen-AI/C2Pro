"""Base classes and data structures for evaluators."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationResult:
    """Result of an evaluation operation.

    Attributes:
        passed: Whether the evaluation passed all assertions
        score: Numeric score from 0.0 to 1.0 representing evaluation quality
        failures: List of failure messages explaining what didn't pass
        details: Optional dictionary with additional evaluation details
    """

    passed: bool
    score: float
    failures: list[str] = field(default_factory=list)
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate score is in valid range."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")

    @classmethod
    def success(cls, score: float = 1.0, details: dict[str, Any] | None = None) -> "EvaluationResult":
        """Create a successful evaluation result.

        Args:
            score: The evaluation score (default 1.0)
            details: Optional additional details

        Returns:
            A passing EvaluationResult
        """
        return cls(passed=True, score=score, failures=[], details=details)

    @classmethod
    def failure(
        cls, failures: list[str], score: float = 0.0, details: dict[str, Any] | None = None
    ) -> "EvaluationResult":
        """Create a failed evaluation result.

        Args:
            failures: List of failure messages
            score: The evaluation score (default 0.0)
            details: Optional additional details

        Returns:
            A failing EvaluationResult
        """
        return cls(passed=False, score=score, failures=failures, details=details)

    def merge(self, other: "EvaluationResult") -> "EvaluationResult":
        """Merge this result with another result.

        The merged result passes only if both pass.
        Scores are averaged. Failures are combined.

        Args:
            other: Another EvaluationResult to merge with

        Returns:
            A new merged EvaluationResult
        """
        merged_details = {}
        if self.details:
            merged_details.update(self.details)
        if other.details:
            merged_details.update(other.details)

        return EvaluationResult(
            passed=self.passed and other.passed,
            score=(self.score + other.score) / 2,
            failures=self.failures + other.failures,
            details=merged_details if merged_details else None,
        )
