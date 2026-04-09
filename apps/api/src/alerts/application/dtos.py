"""
Alert Application DTOs.

Request and Response Data Transfer Objects.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAlertRequest(BaseModel):
    project_id: UUID
    rule_code: str
    category: Literal["SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"]
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    affected_entities: dict = Field(default_factory=dict)


class ReviewAlertRequest(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = ""


class BulkReviewRequest(BaseModel):
    alert_ids: list[str]
    decision: Literal["approve", "reject"]
    comment: str = ""


class BulkDeleteRequest(BaseModel):
    alert_ids: list[str]
    status_filter: str | None = None


class AttachEvidenceRequest(BaseModel):
    type: Literal["note", "screenshot", "document_excerpt"]
    content: str
    source: str = "manual_review"


class ResolveAlertRequest(BaseModel):
    resolution: str
    resolved_by: UUID
    root_cause: str | None = None


class BulkResolveRequest(BaseModel):
    alert_ids: list[str]
    resolution: str
    root_cause: str | None = None


class AlertResponse(BaseModel):
    id: UUID
    project_id: UUID
    tenant_id: UUID
    rule_code: str
    category: str
    severity: str
    message: str
    status: str
    affected_entities: dict = Field(default_factory=dict)
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    root_cause: str | None = None
    sla_policy_name: str | None = None
    sla_due_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int


class AlertHistoryResponse(BaseModel):
    alert_id: str
    items: list[dict]


class BulkOperationResponse(BaseModel):
    processed_count: int
    decision: str | None = None
    warning: str | None = None
    status: str | None = None
    alert_ids: list[str] | None = None


class EvidenceResponse(BaseModel):
    alert_id: str
    evidence_count: int


class DeleteResponse(BaseModel):
    deleted_count: int
