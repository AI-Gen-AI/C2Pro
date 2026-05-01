"""API router for the AI Feedback context."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_202_ACCEPTED

from .schemas import AIFeedbackCreate, AIFeedbackResponse
from .service import AIFeedbackService, get_feedback_service

router = APIRouter(
    prefix="/ai/feedback",
    tags=["AI Feedback"],
)


@router.post(
    "",
    status_code=HTTP_202_ACCEPTED,
    response_model=AIFeedbackResponse,
)
def submit_ai_feedback(
    feedback_data: AIFeedbackCreate,
    feedback_service: AIFeedbackService = Depends(get_feedback_service),
):
    """
    Submits feedback about an AI interaction.

    This endpoint accepts user feedback (e.g., ratings, corrections) and
    associates it with a specific AI interaction trace in LangSmith.
    """
    try:
        feedback_service.submit_feedback(feedback_data)
        return AIFeedbackResponse()
    except Exception as e:
        # In a production system, we'd have more specific error handling.
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {e}",
        )
