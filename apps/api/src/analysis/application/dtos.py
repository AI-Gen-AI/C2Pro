"""
Data Transfer Objects (DTOs) for the Analysis module.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.analysis.domain.enums import AlertSeverity, AlertType


class CoherenceScoreResponse(BaseModel):
    """
    Response model for a project's coherence score.
    Represents the data needed by frontend dashboard widgets.
    """
    project_id: UUID
    score: int | None = Field(None, ge=0, le=100, description="Coherence score from 0 to 100.")
    status: str = Field(..., description="Calculation status (e.g., 'CALCULATED', 'PENDING', 'NOT_FOUND')")
    calculated_at: datetime | None = Field(None, description="Timestamp of the last calculation.")

    breakdown: dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0},
        description="Dictionary with the count of alerts by severity."
    )
    top_drivers: list[str] = Field(
        default_factory=list,
        description="Top 3 reasons or rules that most impacted the score."
    )

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Alert DTOs (public for cross-module use)
# ---------------------------------------------------------------------------


class AlertBase(BaseModel):
    """Base DTO for alert attributes."""

    title: str = Field(..., min_length=1, max_length=255, description="Short title for the alert")
    description: str = Field(..., min_length=1, description="Detailed message explaining the alert")
    severity: AlertSeverity = Field(..., description="Severity level of the alert")
    alert_type: AlertType = Field(default=AlertType.RISK, description="Alert type discriminator (TASK-BCK-026)")
    rule_id: str | None = Field(
        None, max_length=100, description="ID of the coherence rule that triggered this alert"
    )
    category: str | None = Field(None, max_length=50, description="Category of the alert")


class AlertCreate(AlertBase):
    """DTO for creating a new alert."""

    project_id: UUID = Field(..., description="ID of the project this alert belongs to")
    analysis_id: UUID | None = Field(None, description="ID of the analysis that generated this alert")

    # Legal traceability
    source_clause_id: UUID | None = Field(
        None, description="ID of the source clause that triggered this alert (legal traceability)"
    )
    related_clause_ids: list[UUID] | None = Field(
        None, description="IDs of related clauses referenced in this alert"
    )

    # Affected entities
    affected_entities: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON object with affected entities: {documents: [], wbs: [], bom: []}",
    )

    # Evidence and metadata
    alert_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata and evidence for the alert"
    )

    recommendation: str | None = Field(None, description="Suggested action or recommendation")
    impact_level: str | None = Field(None, max_length=20, description="Impact level assessment")
