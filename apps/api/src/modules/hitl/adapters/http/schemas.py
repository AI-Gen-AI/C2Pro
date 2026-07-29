"""Pydantic request/response schemas for HITL endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


class RouteForReviewRequest(BaseModel):
    item_id: UUID
    item_type: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    impact_level: ImpactLevel
    item_data: dict[str, Any] = Field(default_factory=dict)


class ApproveRequest(BaseModel):
    """SECURITY (EPIC-OPS-DOCFLOW Stream C): reviewer identity is never
    accepted from the client — it is derived server-side from the
    authenticated session (Depends(get_current_user)). A client-supplied
    reviewer field here would let any authenticated user forge a review as
    another user, corrupting the HITL audit trail. This body is currently
    empty by design; do not add a reviewer identity field back."""


class RejectRequest(BaseModel):
    """See ApproveRequest docstring: reviewer identity is server-derived,
    never client-supplied."""

    reason: str = Field("", max_length=2000)


class ReviewItemResponse(BaseModel):
    item_id: UUID
    item_type: str
    current_status: ReviewStatus
    confidence: float
    impact_level: ImpactLevel
    approved_by: str | None = None
    approved_at: datetime | None = None
    sla_due_date: datetime
    created_at: datetime
    item_data: dict[str, Any] = {}

    class Config:
        from_attributes = True


class ReviewQueueResponse(BaseModel):
    items: list[ReviewItemResponse]
    total: int


# TASK-BCK-024: Resume workflow after HITL approval/rejection


class ResumeWorkflowRequest(BaseModel):
    """
    Request to resume workflow after HITL decision.

    After a human reviewer makes a decision on a pending review item,
    this endpoint resumes the LangGraph workflow with the decision.

    - **approve**: Workflow resumes from interrupt point with approved status
    - **reject**: Workflow terminates gracefully with rejection reason
    """

    decision: Literal["approve", "reject"] = Field(
        ...,
        description="The reviewer's decision: 'approve' to resume workflow, 'reject' to terminate",
        examples=["approve", "reject"],
    )
    feedback: str = Field(
        "",
        max_length=5000,
        description="Optional feedback or reason for the decision (required for rejections)",
        examples=["Approved - clause looks correct", "Rejected - clause needs revision"],
    )


class ResumeWorkflowResponse(BaseModel):
    """
    Response from workflow resumption.

    Returns the outcome of the resume operation including the final status.
    """

    review_id: UUID = Field(..., description="The ID of the review item that was processed")
    status: str = Field(
        ...,
        description="Result status: 'resumed' (approved), 'rejected' (terminated), or 'terminated_with_errors'",
        examples=["resumed", "rejected"],
    )
    message: str = Field(
        ...,
        description="Human-readable message describing the outcome",
    )
