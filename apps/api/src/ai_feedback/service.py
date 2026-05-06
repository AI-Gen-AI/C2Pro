"""Service layer for the AI Feedback context."""
from __future__ import annotations

from src.core.ai.langsmith_client import LangSmithClient

from .schemas import AIFeedbackCreate


class AIFeedbackService:
    """
    Service for handling AI feedback.

    This service is responsible for taking feedback submissions and sending them
    to the appropriate observability platform (LangSmith).
    """

    def __init__(self):
        self.langsmith_client = LangSmithClient()

    def submit_feedback(self, feedback: AIFeedbackCreate) -> None:
        """
        Submits feedback to LangSmith.

        Args:
            feedback: The feedback data to submit.

        Raises:
            ValueError: If the LangSmith client is not enabled.
        """
        if not self.langsmith_client.enabled:
            # In a real-world scenario, we might want to log this or handle it
            # differently, but for now, we'll just return and do nothing if not enabled.
            return

        self.langsmith_client.create_feedback(
            run_id=feedback.trace_id,
            key=feedback.key,
            score=feedback.score,
            comment=feedback.comment,
        )

def get_feedback_service() -> AIFeedbackService:
    """Factory function for the feedback service."""
    return AIFeedbackService()
