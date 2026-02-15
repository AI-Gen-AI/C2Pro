"""
I11 HITL Domain Entities
Test Suite ID: TS-I11-HITL-DOM-001
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW_REQUIRED = "PENDING_REVIEW_REQUIRED"
    PENDING_REVIEW_CONDITIONAL = "PENDING_REVIEW_CONDITIONAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewItem(BaseModel):
    item_id: UUID
    item_type: str = Field(..., min_length=1)
    current_status: ReviewStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    impact_level: ImpactLevel
    created_at: datetime = Field(default_factory=datetime.now)
    sla_due_date: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    item_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SLACheckResult(BaseModel):
    item_id: UUID
    is_overdue: bool
    new_status: ReviewStatus
    escalation_triggered: bool = False
    message: str

