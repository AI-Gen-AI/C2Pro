"""
C2Pro - Analysis Schemas

Pydantic schemas for analysis, alerts, and coherence checks.
Includes strict validation for coherence scores and legal traceability.

Moved from modules/analysis/schemas.py (2026-01-29)
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.analysis.application.dtos import AlertBase, AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AnalysisStatus, AnalysisType

# ===========================================
# ANALYSIS SCHEMAS
# ===========================================


class AnalysisBase(BaseModel):
    """Base schema for analysis attributes."""

    analysis_type: AnalysisType = Field(
        AnalysisType.COHERENCE, description="Type of analysis to perform"
    )


class AnalysisCreate(AnalysisBase):
    """Schema for creating a new analysis."""

    project_id: UUID = Field(..., description="ID of the project to analyze")


class AnalysisUpdate(BaseModel):
    """Schema for updating an existing analysis (used by agents)."""

    status: AnalysisStatus | None = Field(None, description="Updated analysis status")
    result_json: dict[str, Any] | None = Field(None, description="Complete analysis results")
    coherence_score: int | None = Field(
        None, ge=0, le=100, description="Overall coherence score (0-100)"
    )
    coherence_breakdown: dict[str, Any] | None = Field(
        None, description="Detailed breakdown of coherence score by rule"
    )
    alerts_count: int | None = Field(None, ge=0, description="Number of alerts generated")
    started_at: datetime | None = Field(None, description="When the analysis started")
    completed_at: datetime | None = Field(None, description="When the analysis completed")

    @field_validator("coherence_score")
    @classmethod
    def validate_coherence_score(cls, v: int | None) -> int | None:
        """Validate coherence score is strictly between 0 and 100."""
        if v is not None and not (0 <= v <= 100):
            raise ValueError("coherence_score must be between 0 and 100 (inclusive)")
        return v

    model_config = ConfigDict(extra="forbid")


class AnalysisResponse(AnalysisBase):
    """Schema for analysis response."""

    id: UUID = Field(..., description="Unique ID of the analysis")
    project_id: UUID = Field(..., description="ID of the project analyzed")
    status: AnalysisStatus = Field(..., description="Current status of the analysis")
    result_json: dict[str, Any] | None = Field(None, description="Complete analysis results")
    coherence_score: int | None = Field(
        None, ge=0, le=100, description="Overall coherence score (0-100)"
    )
    coherence_breakdown: dict[str, Any] | None = Field(
        None, description="Detailed breakdown of coherence score by rule"
    )
    alerts_count: int = Field(default=0, description="Number of alerts generated")
    started_at: datetime | None = Field(None, description="When the analysis started")
    completed_at: datetime | None = Field(None, description="When the analysis completed")
    created_at: datetime = Field(..., description="Timestamp of creation")

    @field_validator("coherence_score")
    @classmethod
    def validate_coherence_score(cls, v: int | None) -> int | None:
        """Validate coherence score is strictly between 0 and 100."""
        if v is not None and not (0 <= v <= 100):
            raise ValueError("coherence_score must be between 0 and 100 (inclusive)")
        return v

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# ALERT SCHEMAS
# ===========================================

class AlertUpdate(BaseModel):
    """Schema for updating an existing alert."""

    title: str | None = Field(None, min_length=1, max_length=255, description="Updated title")
    description: str | None = Field(None, min_length=1, description="Updated description")
    severity: AlertSeverity | None = Field(None, description="Updated severity")
    status: AlertStatus | None = Field(None, description="Updated status")
    recommendation: str | None = Field(None, description="Updated recommendation")
    resolution_notes: str | None = Field(None, description="Notes about the resolution")

    model_config = ConfigDict(extra="forbid")


class AlertResponse(AlertBase):
    """Schema for alert response."""

    id: UUID = Field(..., description="Unique ID of the alert")
    project_id: UUID = Field(..., description="ID of the project")
    analysis_id: UUID | None = Field(None, description="ID of the analysis that generated this alert")

    # Legal traceability
    source_clause_id: UUID | None = Field(
        None, description="ID of the source clause (legal traceability)"
    )
    related_clause_ids: list[UUID] | None = Field(None, description="IDs of related clauses")

    # Affected entities and metadata
    affected_entities: dict[str, Any] = Field(
        default_factory=dict, description="Affected entities"
    )
    alert_metadata: dict[str, Any] = Field(default_factory=dict, description="Alert metadata")

    # Additional fields
    recommendation: str | None = Field(None, description="Suggested action")
    impact_level: str | None = Field(None, description="Impact level")

    # Status and resolution
    status: AlertStatus = Field(..., description="Current status of the alert")
    resolved_at: datetime | None = Field(None, description="When the alert was resolved")
    resolved_by: UUID | None = Field(None, description="User who resolved the alert")
    resolution_notes: str | None = Field(None, description="Resolution notes")

    # Timestamps
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# COHERENCE SCORE SCHEMAS
# ===========================================


class CoherenceScoreResponse(BaseModel):
    """Schema for returning the coherence score and its breakdown."""

    coherence_score: int = Field(
        ..., ge=0, le=100, description="Overall coherence score from 0 to 100"
    )
    coherence_breakdown: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed breakdown of the coherence score by categories or rules",
    )
    analysis_id: UUID | None = Field(None, description="ID of the analysis that generated this score")
    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When the score was calculated"
    )

    @field_validator("coherence_score")
    @classmethod
    def validate_coherence_score(cls, v: int) -> int:
        """Validate coherence score is strictly between 0 and 100."""
        if not (0 <= v <= 100):
            raise ValueError("coherence_score must be between 0 and 100 (inclusive)")
        return v


# ===========================================
# DETAILED RESPONSE SCHEMAS
# ===========================================


class AnalysisDetailResponse(AnalysisResponse):
    """Detailed analysis response including associated alerts."""

    alerts: list[AlertResponse] = Field(
        default_factory=list, description="List of alerts generated by this analysis"
    )


__all__ = [
    "AnalysisBase",
    "AnalysisCreate",
    "AnalysisUpdate",
    "AnalysisResponse",
    "AnalysisDetailResponse",
    "AlertBase",
    "AlertCreate",
    "AlertUpdate",
    "AlertResponse",
    "CoherenceScoreResponse",
]
