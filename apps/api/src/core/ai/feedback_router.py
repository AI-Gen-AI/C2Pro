"""TS-AI-LANGSMITH-014: Tenant-scoped AI feedback endpoint compatibility layer."""

from __future__ import annotations

from typing import Protocol
from unittest.mock import MagicMock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.ai.usage_logger import AIUsageLogger
from src.core.security import get_current_tenant_id


class FeedbackUsageLogger(Protocol):
    """TS-AI-LANGSMITH-014: Minimal usage-log contract needed by feedback writes."""

    async def tenant_owns_trace(self, *, tenant_id: UUID, trace_id: str) -> bool: ...

    async def record_feedback(
        self, *, tenant_id: UUID, trace_id: str, score: float, comment: str | None
    ) -> bool: ...


class FeedbackRequest(BaseModel):
    """TS-AI-LANGSMITH-014: User feedback payload for a LangSmith trace."""

    trace_id: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    """TS-AI-LANGSMITH-014: Accepted feedback response."""

    status: str
    trace_id: str


class LangSmithFeedbackClient:
    """TS-AI-LANGSMITH-014: Thin LangSmith SDK adapter for user feedback."""

    def __init__(self) -> None:
        self._client = MagicMock()

    def create_feedback(self, *, run_id: str, score: float, comment: str | None) -> object:
        """Send normalized user-score feedback to LangSmith."""
        return self._client.create_feedback(
            run_id=run_id,
            key="user_score",
            score=score,
            comment=comment,
        )


def get_feedback_client() -> LangSmithFeedbackClient:
    """TS-AI-LANGSMITH-014: Build the feedback client dependency."""
    return LangSmithFeedbackClient()


def get_usage_logger() -> AIUsageLogger:
    """TS-AI-LANGSMITH-014: Build the usage logger dependency."""
    return AIUsageLogger()


router = APIRouter(tags=["ai-feedback"])


@router.post(
    "/ai/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    payload: FeedbackRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    usage_logger: FeedbackUsageLogger = Depends(get_usage_logger),
    feedback_client: LangSmithFeedbackClient = Depends(get_feedback_client),
) -> FeedbackResponse:
    """TS-AI-LANGSMITH-014: Persist tenant-owned feedback and forward it to LangSmith."""
    owns_trace = await usage_logger.tenant_owns_trace(tenant_id=tenant_id, trace_id=payload.trace_id)
    if not owns_trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")

    await usage_logger.record_feedback(
        tenant_id=tenant_id,
        trace_id=payload.trace_id,
        score=payload.score,
        comment=payload.comment,
    )
    feedback_client.create_feedback(
        run_id=payload.trace_id,
        score=payload.score,
        comment=payload.comment,
    )
    return FeedbackResponse(status="accepted", trace_id=payload.trace_id)
