"""TS-AI-LANGSMITH-014: FastAPI endpoint for tenant-scoped LangSmith feedback submission."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.ai.usage_logger import AIUsageLogger
from src.core.security import CurrentTenantId

logger = structlog.get_logger()

router = APIRouter(prefix="/ai", tags=["AI Feedback"])


class FeedbackRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=255)
    score: float = Field(ge=0.0, le=1.0)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    status: str
    trace_id: str


class LangSmithFeedbackClient:
    def __init__(self) -> None:
        try:
            from langsmith import Client
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("langsmith SDK not installed") from exc
        self._client = Client()

    def create_feedback(self, *, run_id: str, score: float, comment: str | None) -> Any:
        return self._client.create_feedback(
            run_id=run_id,
            key="user_score",
            score=score,
            comment=comment,
        )


def get_usage_logger() -> AIUsageLogger:
    return AIUsageLogger()


def get_feedback_client() -> LangSmithFeedbackClient:
    return LangSmithFeedbackClient()


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit end-user feedback for a traced AI run",
)
async def submit_ai_feedback(
    payload: FeedbackRequest,
    tenant_id: CurrentTenantId,
    usage_logger: AIUsageLogger = Depends(get_usage_logger),
    feedback_client: LangSmithFeedbackClient = Depends(get_feedback_client),
) -> FeedbackResponse:
    if not await usage_logger.tenant_owns_trace(tenant_id=tenant_id, trace_id=payload.trace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")

    try:
        feedback_client.create_feedback(
            run_id=payload.trace_id,
            score=payload.score,
            comment=payload.comment,
        )
    except Exception as exc:
        logger.exception("langsmith_feedback_submission_failed", trace_id=payload.trace_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to submit feedback",
        ) from exc

    logger.info(
        "langsmith_feedback_submitted",
        tenant_id=str(tenant_id),
        trace_id=payload.trace_id,
        score=payload.score,
    )
    return FeedbackResponse(status="accepted", trace_id=payload.trace_id)
