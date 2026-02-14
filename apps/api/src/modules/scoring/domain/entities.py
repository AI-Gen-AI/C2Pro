"""
I7 Scoring Domain Entities
Test Suite IDs: TS-I7-SCORE-DOM-001, TS-I7-SCORE-PROFILES-001
"""

from typing import Any

from pydantic import BaseModel, Field


class ScoreConfig(BaseModel):
    """Tenant/project scoring profile used for weighted aggregation."""

    severity_weights: dict[str, float] = Field(default_factory=dict)
    alert_type_multipliers: dict[str, float] = Field(default_factory=dict)
    severity_thresholds: dict[str, float] = Field(default_factory=dict)


class OverallScore(BaseModel):
    """Normalized scoring result returned by domain and application services."""

    score: float = Field(..., ge=0.0)
    severity: str = Field(..., min_length=1)
    explanation: dict[str, Any] = Field(default_factory=dict)

