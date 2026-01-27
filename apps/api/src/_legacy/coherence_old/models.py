"""
C2Pro Coherence Engine - Core Models

This file defines the shared Pydantic models and enums used across
the new coherence engine, such as RuleResult.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class RuleSeverity(str, Enum):
    """Severity of a rule finding."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleStatus(str, Enum):
    """Execution status of a rule."""
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class RuleResult(BaseModel):
    """
    Standardized result object returned by any RuleEvaluator.
    """
    rule_id: str = Field(..., description="Unique identifier for the rule that was run.")
    status: RuleStatus = Field(..., description="The final status of the rule evaluation.")
    severity: RuleSeverity | None = Field(None, description="The severity of the finding, if any.")
    message: str = Field(..., description="A human-readable summary of the result.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed findings or metadata.")

