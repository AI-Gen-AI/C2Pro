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
    reviewer_name: str = Field(..., min_length=1)


class RejectRequest(BaseModel):
    reviewer_name: str = Field(..., min_length=1)
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
