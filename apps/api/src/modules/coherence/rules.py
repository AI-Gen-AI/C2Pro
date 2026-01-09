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

    validated_rules = [Rule(**rule_data) for rule_data in rules_data]
    return validated_rules


if __name__ == "__main__":
    # Example usage and basic test
    example_yaml_content = """
- id: example-rule-1
  description: Checks if project budget is over by 10%
  inputs: ["project.budget.actual", "project.budget.planned"]
  detection_logic: "project.budget.actual > project.budget.planned * 1.1"
  severity: high
  evidence_fields: ["project.budget.actual", "project.budget.planned"]
- id: example-rule-2
  description: Checks for delayed schedule
  inputs: ["project.schedule.status", "project.schedule.end_date"]
  detection_logic: "project.schedule.status == 'delayed'"
  severity: medium
  evidence_fields: ["project.schedule.status"]
"""
    example_yaml_path = "apps/api/src/modules/coherence/example_rules.yaml"
    with open(example_yaml_path, "w", encoding="utf-8") as f:
        f.write(example_yaml_content)

    try:
        loaded_rules = load_rules(example_yaml_path)
        print(f"Successfully loaded {len(loaded_rules)} rules.")
        for rule in loaded_rules:
            print(f"- Rule ID: {rule.id}, Severity: {rule.severity}")
    except Exception as e:
        print(f"Error loading rules: {e}")

    # Clean up example file
    import os

    os.remove(example_yaml_path)
