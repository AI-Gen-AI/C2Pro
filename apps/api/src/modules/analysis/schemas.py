"""
C2Pro - Analysis Schemas

Pydantic schemas for analysis, alerts, and coherence checks.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ===========================================
# PROJECT ANALYSIS SCHEMAS
# ===========================================


class ProjectAnalysisBase(BaseModel):
    analysis_type: str = Field(default="coherence", description="Type of analysis")
    status: str = Field(default="pending", description="Status of the analysis")
    summary: dict[str, Any] | None = Field(None, description="Summary of the analysis results")
    coherence_score: int | None = Field(
        None, ge=0, le=100, description="Coherence score from 0 to 100"
    )


class ProjectAnalysisCreate(ProjectAnalysisBase):
    project_id: UUID


class ProjectAnalysisResponse(ProjectAnalysisCreate):
    id: UUID
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# PROJECT ALERT SCHEMAS
# ===========================================


class ProjectAlertBase(BaseModel):
    rule_id: str = Field(..., description="The ID of the rule that triggered the alert")
    severity: str = Field(
        ..., description="Severity of the alert (e.g., 'critical', 'high', 'medium', 'low')"
    )
    title: str = Field(..., description="A short title for the alert")
    message: str = Field(..., description="A detailed message explaining the alert")
    affected_references: dict[str, Any] | None = Field(
        None, description="JSON object with references to affected parts of documents"
    )
    status: str = Field(
        default="open", description="Status of the alert (e.g., 'open', 'resolved')"
    )


class ProjectAlertCreate(ProjectAlertBase):
    project_id: UUID
    analysis_id: UUID
    clause_id: UUID | None = None


class ProjectAlertResponse(ProjectAlertCreate):
    id: UUID
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: UUID | None

    model_config = ConfigDict(from_attributes=True)
