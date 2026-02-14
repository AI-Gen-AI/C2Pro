"""
I6 Coherence Domain Entities
Test Suite IDs: TS-I6-COH-CONTRACT-001, TS-I6-COH-RULES-001
"""

from datetime import date
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CoherenceAlertEvidence(BaseModel):
    """Dynamic evidence payload for a coherence alert."""

    model_config = {"extra": "allow"}

    def get(self, key: str, default: Any = None) -> Any:
        if self.model_extra and key in self.model_extra:
            return self.model_extra.get(key, default)
        return default


class CoherenceAlert(BaseModel):
    """Standardized payload format for a coherence alert."""

    alert_id: UUID = Field(default_factory=uuid4)
    type: str = Field(..., min_length=1)
    severity: Literal["Critical", "High", "Medium", "Low", "Info"]
    message: str = Field(..., min_length=10)
    evidence: CoherenceAlertEvidence = Field(default_factory=CoherenceAlertEvidence)
    triggered_by_rule: str = Field(..., min_length=1)
    doc_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuleInput(BaseModel):
    """Aggregated input data structure for coherence rules."""

    doc_id: UUID
    schedule_data: dict[str, Any] | None = None
    actual_dates: dict[str, Any] | None = None
    budget_data: dict[str, Any] | None = None
    actual_costs: dict[str, Any] | None = None
    scope_data: dict[str, Any] | None = None
    procurement_items: dict[str, Any] | None = None

