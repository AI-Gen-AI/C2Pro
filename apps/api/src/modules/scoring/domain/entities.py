"""
I7 Scoring Domain Entities
Test Suite IDs: TS-I7-SCORE-DOM-001, TS-I7-SCORE-PROFILES-001
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ScoreConfig(BaseModel):
    """Tenant/project scoring profile used for weighted aggregation."""

    severity_weights: dict[str, float] = Field(default_factory=dict)
    alert_type_multipliers: dict[str, float] = Field(default_factory=dict)
    severity_thresholds: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scoring_contract(self) -> "ScoreConfig":
        required_weights = {"Critical", "High", "Medium", "Low"}
        missing_weights = sorted(required_weights - set(self.severity_weights.keys()))
        if missing_weights:
            raise ValueError(f"severity_weights missing keys: {', '.join(missing_weights)}")

        for severity, weight in self.severity_weights.items():
            if weight < 0:
                raise ValueError(f"severity_weights[{severity}] must be >= 0")

        for alert_type, multiplier in self.alert_type_multipliers.items():
            if multiplier < 0:
                raise ValueError(f"alert_type_multipliers[{alert_type}] must be >= 0")

        required_thresholds = {"Critical", "High", "Medium"}
        missing_thresholds = sorted(required_thresholds - set(self.severity_thresholds.keys()))
        if missing_thresholds:
            raise ValueError(f"severity_thresholds missing keys: {', '.join(missing_thresholds)}")

        critical = self.severity_thresholds["Critical"]
        high = self.severity_thresholds["High"]
        medium = self.severity_thresholds["Medium"]
        if critical < high or high < medium:
            raise ValueError("severity_thresholds must satisfy Critical >= High >= Medium")

        return self


class OverallScore(BaseModel):
    """Normalized scoring result returned by domain and application services."""

    score: float = Field(..., ge=0.0)
    severity: str = Field(..., min_length=1)
    explanation: dict[str, Any] = Field(default_factory=dict)
