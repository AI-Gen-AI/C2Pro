"""Pydantic request/response schemas for HITL endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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
