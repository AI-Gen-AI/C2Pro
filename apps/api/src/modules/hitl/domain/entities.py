"""
I11 HITL Domain Entities
Test Suite ID: TS-I11-HITL-DOM-001
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW_REQUIRED = "PENDING_REVIEW_REQUIRED"
    PENDING_REVIEW_CONDITIONAL = "PENDING_REVIEW_CONDITIONAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


# A human decision is still owed. ESCALATED items were routed to a senior
# reviewer by the SLA job but remain undecided, so they stay actionable
# through the same exact-row fenced resume path (#712 / #714).
AWAITING_DECISION_STATUSES: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.PENDING_REVIEW_REQUIRED,
        ReviewStatus.PENDING_REVIEW_CONDITIONAL,
        ReviewStatus.ESCALATED,
    }
)


class ImpactLevel(StrEnum):
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

