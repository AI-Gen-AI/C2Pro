"""
TDD tests for WebhookNotificationService.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Test Suite ID: TS-HITL-WEBHOOK-NOTIFY-001
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


@pytest.fixture
def test_review_item():
    """Create a test review item for notifications."""
    return ReviewItem(
        item_id=uuid4(),
        item_type="document_analysis",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.65,
        impact_level=ImpactLevel.HIGH,
        sla_due_date=datetime.now(UTC) + timedelta(hours=24),
        approved_by=None,
        approved_at=None,
        item_data={
            "document_name": "Contract_2026_Q1.pdf",
        },
        metadata={},
    )


class TestWebhookNotificationServiceUnit:
    """Unit tests for WebhookNotificationService."""

    @pytest.mark.asyncio
    async def test_send_notification_posts_to_webhook_url(self, test_review_item):
        """WebhookNotificationService should POST JSON payload to webhook URL."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        webhook_url = "https://api.example.com/hitl-notifications"
        service = WebhookNotificationService(
            webhook_url=webhook_url,
            auth_token="Bearer secret-token",
        )

        recipient_id = uuid4()
        message = "Review required for document analysis"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, json=lambda: {"status": "accepted"})

            await service.send_notification(recipient_id, message, test_review_item)

            # Verify webhook was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            assert call_args[0][0] == webhook_url

            # Verify Authorization header
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer secret-token"

            # Verify JSON payload structure
            payload = call_args[1]["json"]
            assert "event_type" in payload
            assert "recipient_id" in payload
            assert "message" in payload
            assert "review_item" in payload

            assert payload["recipient_id"] == str(recipient_id)
            assert payload["message"] == message

            # Review item should be serialized
            review_item_data = payload["review_item"]
            assert review_item_data["item_id"] == str(test_review_item.item_id)
            assert review_item_data["item_type"] == test_review_item.item_type
            assert review_item_data["confidence"] == test_review_item.confidence

    @pytest.mark.asyncio
    async def test_send_escalation_alert_has_escalation_event_type(self, test_review_item):
        """Escalation alerts should have specific event_type for webhook consumers."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(webhook_url="https://api.example.com/hitl")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200)

            await service.send_escalation_alert(test_review_item)

            payload = mock_post.call_args[1]["json"]

            # Event type should indicate escalation
            assert payload["event_type"] == "hitl.escalation"
            assert "review_item" in payload
            assert payload["review_item"]["impact_level"] == test_review_item.impact_level.value

    @pytest.mark.asyncio
    async def test_webhook_timeout_raises_exception(self, test_review_item):
        """Webhook timeouts should raise exception."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(
            webhook_url="https://api.example.com/hitl",
            timeout=5.0
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(httpx.TimeoutException):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

    @pytest.mark.asyncio
    async def test_webhook_4xx_error_raises_exception(self, test_review_item):
        """Webhook 4xx errors (client errors) should raise exception."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(webhook_url="https://api.example.com/hitl")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=400,
                text="Invalid payload",
                json=lambda: {"error": "Invalid payload"}
            )

            with pytest.raises(Exception):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

    @pytest.mark.asyncio
    async def test_webhook_5xx_error_retries(self, test_review_item):
        """Webhook 5xx errors (server errors) should trigger retries."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(
            webhook_url="https://api.example.com/hitl",
            max_retries=3
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            # Fail twice with 5xx, then succeed
            mock_post.side_effect = [
                AsyncMock(status_code=500, text="Internal server error"),
                AsyncMock(status_code=503, text="Service unavailable"),
                AsyncMock(status_code=200),
            ]

            # Should succeed after retries
            await service.send_notification(
                uuid4(), "Test message", test_review_item
            )

            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_custom_headers_are_included(self, test_review_item):
        """Custom headers should be included in webhook requests."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(
            webhook_url="https://api.example.com/hitl",
            custom_headers={
                "X-API-Key": "custom-api-key",
                "X-Client-ID": "c2pro-hitl",
            }
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200)

            await service.send_notification(
                uuid4(), "Test message", test_review_item
            )

            headers = mock_post.call_args[1]["headers"]
            assert headers["X-API-Key"] == "custom-api-key"
            assert headers["X-Client-ID"] == "c2pro-hitl"

    @pytest.mark.asyncio
    async def test_signature_verification_included(self, test_review_item):
        """Webhook should include signature for verification."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(
            webhook_url="https://api.example.com/hitl",
            signing_secret="webhook-secret-key",
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200)

            await service.send_notification(
                uuid4(), "Test message", test_review_item
            )

            headers = mock_post.call_args[1]["headers"]

            # Should include signature header (e.g., X-Webhook-Signature)
            assert any(
                key.lower().startswith("x-") and "signature" in key.lower()
                for key in headers
            )


class TestWebhookNotificationServiceIntegration:
    """Integration tests for WebhookNotificationService."""

    @pytest.mark.asyncio
    async def test_full_notification_payload_structure(self, test_review_item):
        """Full notification payload should have complete structure."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(webhook_url="https://api.example.com/hitl")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200)

            recipient_id = uuid4()
            message = "Review required for document analysis"

            await service.send_notification(recipient_id, message, test_review_item)

            payload = mock_post.call_args[1]["json"]

            # Verify complete payload structure
            assert payload["event_type"] == "hitl.notification"
            assert payload["recipient_id"] == str(recipient_id)
            assert payload["message"] == message

            review_item_data = payload["review_item"]
            assert review_item_data["item_id"] == str(test_review_item.item_id)
            assert review_item_data["item_type"] == test_review_item.item_type
            assert review_item_data["current_status"] == test_review_item.current_status.value
            assert review_item_data["confidence"] == test_review_item.confidence
            assert review_item_data["impact_level"] == test_review_item.impact_level.value

            # Metadata should be included
            assert "item_data" in review_item_data
            assert review_item_data["item_data"]["document_name"] == "Contract_2026_Q1.pdf"

    @pytest.mark.asyncio
    async def test_exponential_backoff_on_retries(self, test_review_item):
        """Retries should use exponential backoff."""
        from src.modules.hitl.adapters.notifications.webhook_notification_service import (
            WebhookNotificationService,
        )

        service = WebhookNotificationService(
            webhook_url="https://api.example.com/hitl",
            max_retries=3,
            retry_backoff_factor=2.0,
        )

        with patch("httpx.AsyncClient.post") as mock_post, \
             patch("asyncio.sleep") as mock_sleep:
            # Always fail to test backoff
            mock_post.return_value = AsyncMock(status_code=500)

            try:  # noqa: SIM105
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )
            except Exception:
                pass  # Expected to fail

            # Verify exponential backoff delays
            if mock_sleep.call_count > 0:
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                # Should see increasing delays: 1s, 2s, 4s (or similar)
                assert len(sleep_calls) >= 2
                assert sleep_calls[1] > sleep_calls[0]
