"""
LLMRulePort - Domain port for LLM-based rule evaluation.

Defines the interface for LLM rule evaluation services.
This stays in the domain layer to maintain hexagonal purity.

Test Suite ID: TS-UD-COH-RUL-001
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from uuid import UUID


@dataclass(frozen=True)
class LLMRuleResult:
    """
    Result from LLM rule evaluation.
    
    Attributes:
        rule_id: The rule that was evaluated.
        clause_id: The clause that was evaluated.
        impact_score: Continuous severity score (0.0-1.0).
        confidence: Certainty level (0.0-1.0).
        severity: Derived severity level.
        category: Coherence category.
        evidence_summary: Human-readable explanation.
        quote: Evidence from the clause text.
        raw_data: Additional metadata.
    """

    rule_id: str
    clause_id: str
    impact_score: float
    confidence: float
    severity: str
    category: str
    evidence_summary: str
    quote: str | None = None
    raw_data: dict[str, Any] | None = None


@runtime_checkable
class LLMRulePort(Protocol):
    """
    Port interface for LLM-based rule evaluation.
    
    This Protocol defines the contract for evaluating 
    coherence rules using LLMs. Concrete implementations
    are in the adapters layer.
    """

    async def evaluate(
        self,
        *,
        rule_id: str,
        rule_name: str,
        rule_description: str,
        detection_logic: str,
        category: str,
        clause_id: str,
        clause_text: str,
        clause_data: dict[str, Any] | None = None,
        tenant_id: UUID | None = None,
    ) -> LLMRuleResult:
        """
        Evaluates a clause against a coherence rule using LLM.
        
        Args:
            rule_id: Unique rule identifier.
            rule_name: Human-readable rule name.
            rule_description: What the rule verifies.
            detection_logic: Detection logic in natural language.
            category: Coherence category.
            clause_id: The clause ID.
            clause_text: The clause text.
            clause_data: Additional structured data.
            tenant_id: Tenant for tracking.
        
        Returns:
            LLMRuleResult with evaluation outcome.
        """
        ...