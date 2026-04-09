"""
TDD tests for SlackNotificationService.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Test Suite ID: TS-HITL-SLACK-NOTIFY-001
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
        sla_due_date=datetime.utcnow() + timedelta(hours=24),
        approved_by=None,
        approved_at=None,
        item_data={
            "document_name": "Contract_2026_Q1.pdf",
            "extraction_confidence": 0.65,
        },
        metadata={},
    )


class TestSlackNotificationServiceUnit:
    """Unit tests for SlackNotificationService."""

    @pytest.mark.asyncio
    async def test_send_notification_posts_to_slack_webhook(self, test_review_item):
        """SlackNotificationService should POST to Slack webhook URL."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        service = SlackNotificationService(webhook_url=webhook_url)

        recipient_id = uuid4()
        message = "Review required for document analysis"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, text="ok")

            await service.send_notification(recipient_id, message, test_review_item)

            # Verify webhook was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            assert call_args[0][0] == webhook_url
            payload = call_args[1]["json"]

            # Verify Slack message format
            assert "text" in payload or "blocks" in payload
            if "text" in payload:
                assert test_review_item.item_type in payload["text"]
            if "blocks" in payload:
                # Verify structured message contains key info
                blocks_str = str(payload["blocks"])
                assert message in blocks_str
                assert str(test_review_item.item_id) in blocks_str

    @pytest.mark.asyncio
    async def test_send_escalation_alert_uses_urgent_formatting(self, test_review_item):
        """Escalation alerts should use urgent Slack formatting (e.g., <!channel>)."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        webhook_url = "https://hooks.slack.com/services/TEST"
        service = SlackNotificationService(webhook_url=webhook_url)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, text="ok")

            await service.send_escalation_alert(test_review_item)

            # Verify urgent formatting
            call_args = mock_post.call_args
            payload = call_args[1]["json"]

            # Should contain channel mention or urgent marker
            payload_str = str(payload)
            assert ("<!channel>" in payload_str or
                    "<!here>" in payload_str or
                    "URGENT" in payload_str or
                    "ESCALATION" in payload_str)

    @pytest.mark.asyncio
    async def test_slack_rate_limit_429_raises_exception(self, test_review_item):
        """Slack rate limiting (429) should raise exception for retry."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        service = SlackNotificationService(webhook_url="https://hooks.slack.com/services/TEST")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=429,
                text="rate_limited",
                headers={"Retry-After": "60"}
            )

            with pytest.raises(Exception):  # Should raise for retry logic
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

    @pytest.mark.asyncio
    async def test_invalid_webhook_url_raises_exception(self, test_review_item):
        """Invalid webhook URLs should raise exception."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        service = SlackNotificationService(webhook_url="https://hooks.slack.com/services/INVALID")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=404, text="invalid_payload")

            with pytest.raises(Exception):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

    @pytest.mark.asyncio
    async def test_message_includes_review_item_details(self, test_review_item):
        """Slack message should include structured review item details."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        service = SlackNotificationService(webhook_url="https://hooks.slack.com/services/TEST")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, text="ok")

            await service.send_notification(
                uuid4(), "Review required", test_review_item
            )

            payload = mock_post.call_args[1]["json"]
            payload_str = str(payload)

            # Verify key details are present
            assert str(test_review_item.item_id) in payload_str
            assert test_review_item.item_type in payload_str
            assert "0.65" in payload_str  # Confidence
            assert "HIGH" in payload_str  # Impact level

    @pytest.mark.asyncio
    async def test_timeout_handling(self, test_review_item):
        """Timeouts should be handled gracefully."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        service = SlackNotificationService(
            webhook_url="https://hooks.slack.com/services/TEST",
            timeout=5.0
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(httpx.TimeoutException):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )


class TestSlackNotificationServiceIntegration:
    """Integration tests for SlackNotificationService."""

    @pytest.mark.asyncio
    async def test_full_notification_flow_with_blocks(self, test_review_item):
        """Full notification flow with Slack blocks formatting."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        service = SlackNotificationService(webhook_url="https://hooks.slack.com/services/TEST")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, text="ok")

            await service.send_notification(
                uuid4(), "Review required for document analysis", test_review_item
            )

            # Verify structured message was sent
            payload = mock_post.call_args[1]["json"]

            # Should have either simple text or blocks format
            assert "text" in payload or "blocks" in payload

            # If using blocks, verify structure
            if "blocks" in payload:
                blocks = payload["blocks"]
                assert isinstance(blocks, list)
                assert len(blocks) > 0

                # Should have header, context, and action sections
                block_types = [block.get("type") for block in blocks]
                assert "section" in block_types or "header" in block_types

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self, test_review_item):
        """Should retry on transient failures (5xx errors)."""
        from src.modules.hitl.adapters.notifications.slack_notification_service import (
            SlackNotificationService,
        )

        service = SlackNotificationService(
            webhook_url="https://hooks.slack.com/services/TEST",
            max_retries=3
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            # Fail twice, then succeed
            mock_post.side_effect = [
                AsyncMock(status_code=500, text="internal_error"),
                AsyncMock(status_code=503, text="service_unavailable"),
                AsyncMock(status_code=200, text="ok"),
            ]

            # Should succeed after retries
            await service.send_notification(
                uuid4(), "Test message", test_review_item
            )

            # Verify retries were attempted
            assert mock_post.call_count == 3
