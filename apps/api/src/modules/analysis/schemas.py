"""
C2Pro - Analysis Schemas

Pydantic schemas for analysis, alerts, and coherence checks.
Includes strict validation for coherence scores and legal traceability.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.analysis.adapters.persistence.models import (
    AlertSeverity,
    AlertStatus,
    AnalysisStatus,
    AnalysisType,
)

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

    status: Optional[AnalysisStatus] = Field(None, description="Updated analysis status")
    result_json: Optional[Dict[str, Any]] = Field(None, description="Complete analysis results")
    coherence_score: Optional[int] = Field(
        None, ge=0, le=100, description="Overall coherence score (0-100)"
    )
    coherence_breakdown: Optional[Dict[str, Any]] = Field(
        None, description="Detailed breakdown of coherence score by rule"
    )
    alerts_count: Optional[int] = Field(None, ge=0, description="Number of alerts generated")
    started_at: Optional[datetime] = Field(None, description="When the analysis started")
    completed_at: Optional[datetime] = Field(None, description="When the analysis completed")

    @field_validator("coherence_score")
    @classmethod
    def validate_coherence_score(cls, v: Optional[int]) -> Optional[int]:
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
    result_json: Optional[Dict[str, Any]] = Field(None, description="Complete analysis results")
    coherence_score: Optional[int] = Field(
        None, ge=0, le=100, description="Overall coherence score (0-100)"
    )
    coherence_breakdown: Optional[Dict[str, Any]] = Field(
        None, description="Detailed breakdown of coherence score by rule"
    )
    alerts_count: int = Field(default=0, description="Number of alerts generated")
    started_at: Optional[datetime] = Field(None, description="When the analysis started")
    completed_at: Optional[datetime] = Field(None, description="When the analysis completed")
    created_at: datetime = Field(..., description="Timestamp of creation")

    @field_validator("coherence_score")
    @classmethod
    def validate_coherence_score(cls, v: Optional[int]) -> Optional[int]:
        """Validate coherence score is strictly between 0 and 100."""
        if v is not None and not (0 <= v <= 100):
            raise ValueError("coherence_score must be between 0 and 100 (inclusive)")
        return v

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# ALERT SCHEMAS
# ===========================================


class AlertBase(BaseModel):
    """Base schema for alert attributes."""

    title: str = Field(..., min_length=1, max_length=255, description="Short title for the alert")
    description: str = Field(..., min_length=1, description="Detailed message explaining the alert")
    severity: AlertSeverity = Field(..., description="Severity level of the alert")
    rule_id: Optional[str] = Field(
        None, max_length=100, description="ID of the coherence rule that triggered this alert"
    )
    category: Optional[str] = Field(None, max_length=50, description="Category of the alert")


class AlertCreate(AlertBase):
    """Schema for creating a new alert (used by AI agents)."""

    project_id: UUID = Field(..., description="ID of the project this alert belongs to")
    analysis_id: Optional[UUID] = Field(None, description="ID of the analysis that generated this alert")

    # CRITICAL: Legal traceability (ROADMAP §5.3)
    source_clause_id: Optional[UUID] = Field(
        None, description="ID of the source clause that triggered this alert (legal traceability)"
    )
    related_clause_ids: Optional[List[UUID]] = Field(
        None, description="IDs of related clauses referenced in this alert"
    )

    # Affected entities
    affected_entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON object with affected entities: {documents: [], wbs: [], bom: []}"
    )

    # Evidence and metadata
    alert_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata and evidence for the alert"
    )

    recommendation: Optional[str] = Field(None, description="Suggested action or recommendation")
    impact_level: Optional[str] = Field(None, max_length=20, description="Impact level assessment")


class AlertUpdate(BaseModel):
    """Schema for updating an existing alert."""

    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated title")
    description: Optional[str] = Field(None, min_length=1, description="Updated description")
    severity: Optional[AlertSeverity] = Field(None, description="Updated severity")
    status: Optional[AlertStatus] = Field(None, description="Updated status")
    recommendation: Optional[str] = Field(None, description="Updated recommendation")
    resolution_notes: Optional[str] = Field(None, description="Notes about the resolution")

    model_config = ConfigDict(extra="forbid")


class AlertResponse(AlertBase):
    """Schema for alert response."""

    id: UUID = Field(..., description="Unique ID of the alert")
    project_id: UUID = Field(..., description="ID of the project")
    analysis_id: Optional[UUID] = Field(None, description="ID of the analysis that generated this alert")

    # Legal traceability
    source_clause_id: Optional[UUID] = Field(
        None, description="ID of the source clause (legal traceability)"
    )
    related_clause_ids: Optional[List[UUID]] = Field(None, description="IDs of related clauses")

    # Affected entities and metadata
    affected_entities: Dict[str, Any] = Field(
        default_factory=dict, description="Affected entities"
    )
    alert_metadata: Dict[str, Any] = Field(default_factory=dict, description="Alert metadata")

    # Additional fields
    recommendation: Optional[str] = Field(None, description="Suggested action")
    impact_level: Optional[str] = Field(None, description="Impact level")

    # Status and resolution
    status: AlertStatus = Field(..., description="Current status of the alert")
    resolved_at: Optional[datetime] = Field(None, description="When the alert was resolved")
    resolved_by: Optional[UUID] = Field(None, description="User who resolved the alert")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")

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
    coherence_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed breakdown of the coherence score by categories or rules",
    )
    analysis_id: Optional[UUID] = Field(None, description="ID of the analysis that generated this score")
    calculated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the score was calculated"
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

    alerts: List[AlertResponse] = Field(
        default_factory=list, description="List of alerts generated by this analysis"
    )


# ===========================================
# LEGACY SCHEMAS (for backward compatibility)
# ===========================================


class ProjectAnalysisBase(BaseModel):
    """Legacy base schema - use AnalysisBase instead."""

    analysis_type: str = Field(default="coherence", description="Type of analysis")
    status: str = Field(default="pending", description="Status of the analysis")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary of the analysis results")
    coherence_score: Optional[int] = Field(
        None, ge=0, le=100, description="Coherence score from 0 to 100"
    )
    evidence_json: Dict[str, Any] = Field(
        default_factory=dict, description="JSON object containing evidence details for the analysis"
    )


class ProjectAnalysisCreate(ProjectAnalysisBase):
    """Legacy create schema - use AnalysisCreate instead."""

    project_id: UUID


class ProjectAnalysisResponse(ProjectAnalysisCreate):
    """Legacy response schema - use AnalysisResponse instead."""

    id: UUID
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ProjectAlertBase(BaseModel):
    """Legacy alert base schema - use AlertBase instead."""

    rule_id: str = Field(..., description="The ID of the rule that triggered the alert")
    severity: str = Field(
        ..., description="Severity of the alert (e.g., 'critical', 'high', 'medium', 'low')"
    )
    title: str = Field(..., description="A short title for the alert")
    message: str = Field(..., description="A detailed message explaining the alert")
    affected_references: Optional[Dict[str, Any]] = Field(
        None, description="JSON object with references to affected parts of documents"
    )
    status: str = Field(
        default="open", description="Status of the alert (e.g., 'open', 'resolved')"
    )
    evidence_json: Dict[str, Any] = Field(
        default_factory=dict, description="JSON object containing evidence details for the alert"
    )


class ProjectAlertCreate(ProjectAlertBase):
    """Legacy alert create schema - use AlertCreate instead."""

    project_id: UUID
    analysis_id: UUID
    clause_id: Optional[UUID] = None


class ProjectAlertResponse(ProjectAlertCreate):
    """Legacy alert response schema - use AlertResponse instead."""

    id: UUID
    created_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[UUID]

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# EXTRACTION SCHEMAS
# ===========================================


class ExtractionBase(BaseModel):
    """Base schema for extraction attributes."""

    extraction_type: Optional[str] = Field(
        None, max_length=50, description="Type of extraction (contract_metadata, milestones, budget_items)"
    )
    data_json: Dict[str, Any] = Field(
        ..., description="Extracted data as JSON object"
    )
    confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="AI confidence score (0.0-1.0)"
    )


class ExtractionCreate(ExtractionBase):
    """Schema for creating a new extraction."""

    document_id: UUID = Field(..., description="ID of the document this extraction belongs to")

    # AI tracking (ROADMAP §6.2)
    model_version: Optional[str] = Field(
        None, max_length=50, description="Version of AI model used for extraction"
    )
    tokens_used: Optional[int] = Field(None, ge=0, description="Number of tokens used")
    cost_usd: Optional[float] = Field(None, ge=0, description="Cost in USD for this extraction")


class ExtractionUpdate(BaseModel):
    """Schema for updating an existing extraction."""

    extraction_type: Optional[str] = Field(None, max_length=50)
    data_json: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class ExtractionResponse(ExtractionBase):
    """Schema for extraction response."""

    id: UUID = Field(..., description="Unique ID of the extraction")
    document_id: UUID = Field(..., description="ID of the document")

    # AI tracking
    model_version: Optional[str] = Field(None, description="AI model version")
    tokens_used: Optional[int] = Field(None, description="Tokens used")
    cost_usd: Optional[float] = Field(None, description="Cost in USD")

    # Computed property
    confidence_level: str = Field(
        "unknown", description="Confidence level (high, medium, low, unknown)"
    )

    created_at: datetime = Field(..., description="Timestamp of creation")

    model_config = ConfigDict(from_attributes=True)


class ExtractionListResponse(BaseModel):
    """Schema for list of extractions with pagination."""

    items: List[ExtractionResponse] = Field(
        default_factory=list, description="List of extractions"
    )
    total: int = Field(..., description="Total number of extractions")
    document_id: UUID = Field(..., description="Document ID these extractions belong to")
