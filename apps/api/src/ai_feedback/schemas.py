"""Pydantic schemas for the AI Feedback context."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AIFeedbackCreate(BaseModel):
    """Schema for creating a new AI feedback entry."""

    trace_id: str = Field(
        ...,
        description="The LangSmith trace ID of the AI interaction that this feedback refers to.",
        examples=["e2a6f3b6-1b6a-4b0a-8a0a-9c7d8f3b6a1e"],
    )

    key: str = Field(
        "user_feedback",
        description="The key or name for the feedback, used for grouping in LangSmith.",
        examples=["user_rating", "correction"],
    )

    score: float | None = Field(
        None,
        description="A numerical score for the feedback, e.g., a rating from 0.0 to 1.0.",
        ge=0.0,
        le=1.0,
    )

    comment: str | None = Field(
        None,
        description="A free-text comment providing qualitative feedback or a correction.",
        max_length=5000,
    )

class AIFeedbackResponse(BaseModel):
    """Schema for the response after submitting feedback."""

    message: str = "Feedback submitted successfully."
