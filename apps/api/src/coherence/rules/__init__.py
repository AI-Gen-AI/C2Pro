"""
Rule loader and schema for the coherence engine.
"""

from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

# Evaluator types
EvaluatorType = Literal["deterministic", "llm"]


class Rule(BaseModel):
    id: str = Field(..., description="Unique identifier for the rule.")
    description: str = Field(..., description="A brief description of what the rule checks.")
    inputs: list[str] = Field(
        default_factory=list, description="List of project context fields this rule depends on."
    )
    detection_logic: str = Field(
        default="", description="Placeholder for the logic that detects the condition."
    )
    severity: Literal["critical", "high", "medium", "low"] = Field(
        ..., description="The severity of the alert if the rule is triggered."
    )
    evidence_fields: list[str] = Field(
        default_factory=list,
        description="List of fields from the project context that provide evidence for the alert.",
    )
    evaluator_type: EvaluatorType = Field(
        default="deterministic",
        description="Type of evaluator: 'deterministic' for code-based, 'llm' for AI-based.",
    )
    category: Optional[str] = Field(
        default="general",
        description="Category of the rule (legal, financial, technical, schedule, scope, quality).",
    )
    name: Optional[str] = Field(
        default=None,
        description="Human-readable name for the rule. If None, uses id.",
    )

    @property
    def display_name(self) -> str:
        """Returns the display name of the rule."""
        return self.name or self.id

    @property
    def is_llm_rule(self) -> bool:
        """Returns True if this rule uses LLM for evaluation."""
        return self.evaluator_type == "llm"


class _StrictRule(Rule):
    """Rule subclass with stricter validation for YAML loading."""

    inputs: list[str] = Field(
        ..., description="List of project context fields this rule depends on."
    )


def load_rules(file_path: str) -> list[Rule]:
    """
    Loads rules from a YAML file and validates them against the Rule Pydantic model.

    Uses strict validation that requires 'inputs' field when loading from files.
    """
    with open(file_path, encoding="utf-8") as f:
        rules_data = yaml.safe_load(f)

    if not isinstance(rules_data, list):
        raise ValueError("YAML file must contain a list of rules.")

    return [_StrictRule(**rule_data) for rule_data in rules_data]
