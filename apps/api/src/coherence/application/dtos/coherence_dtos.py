"""
Coherence calculation DTOs.

Refers to Suite ID: TS-UA-COH-UC-001.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from src.coherence.domain.alert_mapping import CoherenceAlert
from src.coherence.domain.category_weights import CoherenceCategory


class AlertAction(str, Enum):
    """Actions that can be taken on alerts."""

    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ACKNOWLEDGED = "acknowledged"


class CalculateCoherenceCommand(BaseModel):
    """Input command for coherence calculation."""

    project_id: UUID
    contract_price: float = 0.0
    bom_items: list[dict[str, object]] = Field(default_factory=list)
    scope_defined: bool = True
    schedule_within_contract: bool = True
    technical_consistent: bool = True
    legal_compliant: bool = True
    quality_standard_met: bool = True
    custom_weights: dict[CoherenceCategory, float] | None = None
    document_count: int = 0


class CategoryScoreDetail(BaseModel):
    """Per-category score detail."""

    category: CoherenceCategory
    score: int
    violations: list[str]


class CoherenceCalculationResult(BaseModel):
    """Output result from coherence calculation."""

    project_id: UUID
    global_score: int
    category_scores: dict[CoherenceCategory, int]
    category_details: list[CategoryScoreDetail]
    alerts: list[CoherenceAlert]
    is_gaming_detected: bool
    gaming_violations: list[str]
    penalty_points: int


class RecalculateOnAlertCommand(BaseModel):
    """Input command for recalculating coherence after alert action."""

    project_id: UUID
    alert_ids: list[str] = Field(default_factory=list)
    alert_action: AlertAction
    action_timestamp: datetime | None = None
    # Original project data needed for recalculation
    contract_price: float = 0.0
    bom_items: list[dict[str, object]] = Field(default_factory=list)
    scope_defined: bool = True
    schedule_within_contract: bool = True
    technical_consistent: bool = True
    legal_compliant: bool = True
    quality_standard_met: bool = True
    custom_weights: dict[CoherenceCategory, float] | None = None
    document_count: int = 0


class RecalculateOnAlertResult(BaseModel):
    """Output result from recalculation after alert action."""

    project_id: UUID
    previous_global_score: int
    new_global_score: int
    score_delta: int
    previous_category_scores: dict[CoherenceCategory, int]
    new_category_scores: dict[CoherenceCategory, int]
    category_details: list[CategoryScoreDetail]
    remaining_alerts: list[CoherenceAlert]
    resolved_alert_ids: list[str]
    is_gaming_detected: bool
    gaming_violations: list[str]
    penalty_points: int
    recalculation_triggered: bool
