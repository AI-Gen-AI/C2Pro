"""
Rule loader and schema for the coherence engine.
"""

from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Rule(BaseModel):
    id: str = Field(..., description="Unique identifier for the rule.")
    description: str = Field(..., description="A brief description of what the rule checks.")
    inputs: list[str] = Field(
        ..., description="List of project context fields this rule depends on."
    )
    detection_logic: str = Field(
        ..., description="Placeholder for the logic that detects the condition."
    )
    severity: Literal["critical", "high", "medium", "low"] = Field(
        ..., description="The severity of the alert if the rule is triggered."
    )
    evidence_fields: list[str] = Field(
        ...,
        description="List of fields from the project context that provide evidence for the alert.",
    )


def load_rules(file_path: str) -> list[Rule]:
    """
    Loads rules from a YAML file and validates them against the Rule Pydantic model.
    """
    with open(file_path, encoding="utf-8") as f:
        rules_data = yaml.safe_load(f)

    if not isinstance(rules_data, list):
        raise ValueError("YAML file must contain a list of rules.")

    return [Rule(**rule_data) for rule_data in rules_data]
