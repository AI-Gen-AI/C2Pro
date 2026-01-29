# apps/api/src/coherence/rules_engine/base.py
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from ..models import Clause


class Finding(BaseModel):
    """
    An internal data object representing a potential issue found by a RuleEvaluator.
    This is a precursor to a formatted Alert.
    """

    triggered_clause: Clause = Field(
        ..., description="The specific clause that triggered the finding."
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Raw data points that are relevant to the finding."
    )
    # In the future, this could include confidence scores, etc.


class RuleEvaluator(ABC):
    """
    Abstract base class for all rule evaluators.

    Each concrete implementation of this class is responsible for the logic
    of a single coherence rule.
    """

    @abstractmethod
    def evaluate(self, clause: Clause) -> Finding | None:
        """
        Evaluates a single clause against the specific rule's logic.

        Args:
            clause: The clause to evaluate.

        Returns:
            A Finding object if the rule's conditions are met, otherwise None.
        """
        raise NotImplementedError
