"""
TDD tests for EmailNotificationService.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Test Suite ID: TS-HITL-EMAIL-NOTIFY-001
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


class _AnyRecipientResolver:
    """Test resolver — maps any UUID to a fixed email."""

    def __init__(self, email: str = "reviewer@example.com") -> None:
        self._email = email

    async def resolve_email(self, recipient_id: UUID) -> str | None:
        return self._email


@pytest.fixture
def resolver() -> _AnyRecipientResolver:
    return _AnyRecipientResolver()


@pytest.fixture
def test_review_item():
    """Create a test review item for notifications."""
    return ReviewItem(
        item_id=uuid4(),
        item_type="document_analysis",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.65,
        impact_level=ImpactLevel.HIGH,
        sla_due_date=datetime.now(timezone.utc) + timedelta(hours=24),
        approved_by=None,
        approved_at=None,
        item_data={
            "document_name": "Contract_2026_Q1.pdf",
            "extraction_confidence": 0.65,
            "stakeholders": ["Alice", "Bob"],
        },
        metadata={
            "project_id": str(uuid4()),
            "document_id": str(uuid4()),
        },
    )


class TestEmailNotificationServiceUnit:
    """Unit tests for EmailNotificationService."""

    @pytest.mark.asyncio
    async def test_send_notification_sends_email_via_smtp(self, test_review_item, resolver):
        """EmailNotificationService should send email via SMTP server."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="notifications@example.com",
            smtp_password="secret",
            from_email="notifications@example.com",
            recipient_resolver=resolver,
        )

        recipient_id = uuid4()
        message = "Review required for document analysis"

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            await service.send_notification(recipient_id, message, test_review_item)

            # Verify SMTP connection was established
            mock_smtp_class.assert_called_once_with(hostname="smtp.example.com", port=587)
            mock_smtp.connect.assert_awaited_once()
            mock_smtp.login.assert_awaited_once_with("notifications@example.com", "secret")

            # Verify email was sent
            mock_smtp.send_message.assert_awaited_once()
            sent_message = mock_smtp.send_message.call_args[0][0]
            # Resolver maps recipient UUID → email. Assert on the resolved
            # email rather than the raw UUID (the old str(recipient_id)
            # behaviour was a bug; notifications never routed).
            assert sent_message["To"] == "reviewer@example.com"
            assert sent_message["Subject"] is not None
            assert message in sent_message.get_content()

            mock_smtp.quit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_escalation_alert_sends_urgent_email(self, test_review_item, resolver):
        """Escalation alerts should have urgent priority and specific formatting."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="notifications@example.com",
            smtp_password="secret",
            from_email="notifications@example.com",
            recipient_resolver=resolver,
        )

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            await service.send_escalation_alert(test_review_item)

            # Verify urgent email was sent
            mock_smtp.send_message.assert_awaited_once()
            sent_message = mock_smtp.send_message.call_args[0][0]
            assert "URGENT" in sent_message["Subject"] or "ESCALATION" in sent_message["Subject"]
            assert "HIGH" in sent_message.get_content()  # Impact level
            assert str(test_review_item.item_id) in sent_message.get_content()

    @pytest.mark.asyncio
    async def test_smtp_connection_failure_raises_exception(self, test_review_item, resolver):
        """SMTP connection failures should raise clear exceptions."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="invalid.smtp.server",
            smtp_port=587,
            smtp_user="test@example.com",
            smtp_password="wrong",
            from_email="test@example.com",
            recipient_resolver=resolver,
        )

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.connect.side_effect = ConnectionRefusedError("Connection refused")
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            with pytest.raises(ConnectionRefusedError):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

    @pytest.mark.asyncio
    async def test_authentication_failure_raises_exception(self, test_review_item, resolver):
        """SMTP authentication failures should raise clear exceptions."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="test@example.com",
            smtp_password="wrong",
            from_email="test@example.com",
            recipient_resolver=resolver,
        )

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.login.side_effect = Exception("Authentication failed")
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            with pytest.raises(Exception, match="Authentication failed"):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

    @pytest.mark.asyncio
    async def test_email_contains_review_item_details(self, test_review_item, resolver):
        """Email body should contain all relevant review item details."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="notifications@example.com",
            smtp_password="secret",
            from_email="notifications@example.com",
            recipient_resolver=resolver,
        )

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            await service.send_notification(
                uuid4(), "Review required", test_review_item
            )

            sent_message = mock_smtp.send_message.call_args[0][0]
            body = sent_message.get_content()

            # Verify key details are present
            assert str(test_review_item.item_id) in body
            assert test_review_item.item_type in body
            assert "HIGH" in body  # Impact level
            assert "0.65" in body  # Confidence
            assert "Contract_2026_Q1.pdf" in body  # Document name


class TestEmailNotificationServiceIntegration:
    """Integration tests for EmailNotificationService with real SMTP (mocked)."""

    @pytest.mark.asyncio
    async def test_full_notification_flow_with_retry(self, test_review_item, resolver):
        """Full notification flow with retry on transient failures."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="notifications@example.com",
            smtp_password="secret",
            from_email="notifications@example.com",
            max_retries=3,
            recipient_resolver=resolver,
        )

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp

        # Simulate transient failure then success
        mock_smtp.send_message.side_effect = [
            Exception("Temporary failure"),
            None,  # Success on retry
        ]
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            # Should succeed after retry
            await service.send_notification(
                uuid4(), "Test message", test_review_item
            )

            # Verify retry was attempted
            assert mock_smtp.send_message.await_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_raises_exception(self, test_review_item, resolver):
        """After max retries, should raise exception."""
        from src.modules.hitl.adapters.notifications.email_notification_service import (
            EmailNotificationService,
        )

        service = EmailNotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="notifications@example.com",
            smtp_password="secret",
            from_email="notifications@example.com",
            max_retries=2,
            recipient_resolver=resolver,
        )

        mock_smtp_class = Mock()
        mock_smtp = AsyncMock()
        mock_smtp_class.return_value = mock_smtp

        # Always fail
        mock_smtp.send_message.side_effect = Exception("Permanent failure")
        with patch(
            "src.modules.hitl.adapters.notifications.email_notification_service.aiosmtplib",
            new=SimpleNamespace(SMTP=mock_smtp_class),
        ):

            with pytest.raises(Exception, match="Permanent failure"):
                await service.send_notification(
                    uuid4(), "Test message", test_review_item
                )

            # Verify retries were attempted
            assert mock_smtp.send_message.await_count == 3  # Initial + 2 retries
