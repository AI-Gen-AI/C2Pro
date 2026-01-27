"""
C2Pro Coherence Engine - Evaluator Interface

This file defines the abstract base classes for the rule evaluation system.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from pydantic import BaseModel, Field
from .models import RuleResult


class RuleEvaluatorContext(BaseModel):
    """
    Data context provided to a rule evaluator.

    This object acts as a generic container for all data needed for a rule evaluation run.
    Subclasses of evaluators can expect specific keys to be present in the `data` dictionary.
    """
    project_id: str = Field(..., description="The ID of the project being evaluated.")
    tenant_id: str = Field(..., description="The ID of the tenant owning the project.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary data for the rule.")


class RuleEvaluator(ABC):
    """
    Abstract base class for all rule evaluators in the coherence engine.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """A unique identifier for the rule (e.g., 'COH-001')."""
        raise NotImplementedError

    @abstractmethod
    async def evaluate(self, context: RuleEvaluatorContext, db: AsyncSession) -> RuleResult:
        """
        Evaluates a rule against the given context.

        Args:
            context: The data context for the evaluation.
            db: The database session for data access.

        Returns:
            A RuleResult object summarizing the outcome.
        """
        raise NotImplementedError

