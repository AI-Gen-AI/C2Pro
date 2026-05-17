# apps/api/src/coherence/rules_engine/base.py
"""
Base classes for coherence rule evaluators.

v0.3 adds:
- FindingSignal for continuous scoring (0.0-1.0 impact_score)
- evaluate_v3() method returning FindingSignal
- Rule metadata attributes (rule_id, rule_name, category)
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from ..models import Clause, CoherenceCategory, FindingSignal, impact_to_severity
from enum import Enum

from .category_utils import infer_category


class ApplicabilityState(Enum):
    """Whether a rule could meaningfully run against a clause."""

    EVALUATED = "EVALUATED"
    SKIPPED_MISSING_INPUTS = "SKIPPED_MISSING_INPUTS"
    SKIPPED_DISABLED = "SKIPPED_DISABLED"


class Finding(BaseModel):
    """
    An internal data object representing a potential issue found by a RuleEvaluator.
    This is a precursor to a formatted Alert.

    NOTE: This class is retained for backward compatibility. New evaluators
    should use evaluate_v3() which returns FindingSignal instead.
    """

    triggered_clause: Clause = Field(
        ..., description="The specific clause that triggered the finding."
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Raw data points that are relevant to the finding."
    )


class RuleEvaluator(ABC):
    """
    Abstract base class for all rule evaluators.

    Each concrete implementation of this class is responsible for the logic
    of a single coherence rule.

    v0.3 Attributes (class-level):
        rule_id: Unique identifier (e.g., "DET-BUD-OVERRUN")
        rule_name: Human-readable name
        category: One of the 6 coherence categories
    """

    # Class-level metadata (override in subclasses)
    rule_id: ClassVar[str] = "UNKNOWN"
    rule_name: ClassVar[str] = "Unknown Rule"
    category: ClassVar[CoherenceCategory] = "SCOPE"

    def applicability(self, clause: Clause) -> ApplicabilityState:
        """
        Whether this rule can meaningfully evaluate `clause`.

        Conservative default: EVALUATED only if the clause's inferred
        category matches this rule's category; otherwise the rule had no
        real evidence to assess, so SKIPPED_MISSING_INPUTS. Field-dependent
        rules override this to also require their structured inputs.
        """
        if infer_category(clause) == self.category:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    @abstractmethod
    def evaluate(self, clause: Clause) -> Finding | None:
        """
        Evaluates a single clause against the specific rule's logic.

        Args:
            clause: The clause to evaluate.

        Returns:
            A Finding object if the rule's conditions are met, otherwise None.

        NOTE: For new evaluators, implement evaluate_v3() instead.
        This method is retained for backward compatibility.
        """
        raise NotImplementedError

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        """
        Evaluates a clause and returns a continuous-scored FindingSignal.

        This is the v0.3 evaluation method that returns:
        - impact_score: 0.0 (no issue) to 1.0 (catastrophic)
        - confidence: 1.0 for deterministic rules
        - severity: Derived from impact_score via impact_to_severity()

        Args:
            clause: The clause to evaluate.

        Returns:
            FindingSignal if issue detected, None otherwise.

        Default implementation wraps evaluate() for backward compat.
        Override this method in new evaluators for continuous scoring.
        """
        finding = self.evaluate(clause)
        if finding is None:
            return None

        # Default mapping: binary finding → medium impact
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            source="deterministic",
            impact_score=0.50,  # Default for legacy binary findings
            confidence=1.0,
            severity="medium",
            category=self.category,
            evidence_summary=f"Rule {self.rule_id} triggered",
            quote=clause.text[:200] if clause.text else "",
            raw_data=finding.raw_data,
        )


# Re-export for convenience
__all__ = [
    "Finding",
    "FindingSignal",
    "RuleEvaluator",
    "impact_to_severity",
]
