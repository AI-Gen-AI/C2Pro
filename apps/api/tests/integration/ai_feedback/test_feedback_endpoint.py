"""Integration tests for the AI feedback endpoint."""
from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest
from httpx import AsyncClient

# Import your FastAPI app
from src.main import app


@pytest.mark.asyncio
@patch("src.ai_feedback.service.AIFeedbackService.submit_feedback")
async def test_submit_feedback_success(
    mock_submit_feedback,
    authenticated_client: AsyncClient,
    mock_lookup_tenant_by_id,
):
    """Test successful feedback submission."""
    response = await authenticated_client.post(
        "/api/v1/ai/feedback",
        json={"trace_id": "trace-123", "key": "user-rating", "score": 1.0},
    )
    assert response.status_code == 202
    assert response.json() == {"message": "Feedback submitted successfully."}
    mock_submit_feedback.assert_called_once()

@pytest.mark.asyncio
async def test_submit_feedback_invalid_payload(
    authenticated_client: AsyncClient,
    mock_lookup_tenant_by_id,
):
    """Test with an invalid payload."""
    # trace_id is missing
    response = await authenticated_client.post(
        "/api/v1/ai/feedback",
        json={"key": "user-rating", "score": 1.0},
    )
    assert response.status_code == 422  # Unprocessable Entity

@pytest.mark.asyncio
async def test_submit_feedback_unauthenticated():
    """Test that unauthenticated requests are rejected."""
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/feedback",
        json={"trace_id": "trace-123", "key": "user-rating", "score": 1.0},
    )
    assert response.status_code == 401


@patch("src.core.ai.langsmith_client.LangSmithClient.create_feedback")
@patch("src.core.ai.langsmith_client.LangSmithClient.enabled", new_callable=PropertyMock, return_value=True)
def test_feedback_service_calls_langsmith_client(mock_enabled, mock_create_feedback):
    """Test that the service calls the LangSmith client."""
    from src.ai_feedback.schemas import AIFeedbackCreate
    from src.ai_feedback.service import AIFeedbackService

    service = AIFeedbackService()
    feedback_data = AIFeedbackCreate(
        trace_id="trace-123",
        key="test-key",
        score=0.5,
        comment="test comment"
    )

    service.submit_feedback(feedback_data)
    mock_create_feedback.assert_called_once_with(
        run_id="trace-123",
        key="test-key",
        score=0.5,
        comment="test comment"
    )
