"""
TDD tests for NotificationRouter (strategy pattern).
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Test Suite ID: TS-HITL-NOTIFY-ROUTER-001
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
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
        item_data={},
        metadata={},
    )


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


class TestNotificationRouterUnit:
    """Unit tests for NotificationRouter."""

    @pytest.mark.asyncio
    async def test_routes_to_email_when_email_enabled(self, test_review_item, tenant_id):
        """NotificationRouter should route to email service when email is enabled."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_email_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email"],
            "email_recipients": ["pm@example.com"],
        }

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=None,
            webhook_service=None,
            config_repository=mock_config_repo,
        )

        recipient_id = uuid4()
        message = "Review required"

        await router.send_notification(recipient_id, message, test_review_item, tenant_id)

        # Verify email service was called
        mock_email_service.send_notification.assert_awaited_once_with(
            recipient_id, message, test_review_item, tenant_id
        )

    @pytest.mark.asyncio
    async def test_routes_to_slack_when_slack_enabled(self, test_review_item, tenant_id):
        """NotificationRouter should route to Slack service when Slack is enabled."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_slack_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["slack"],
            "slack_webhook_url": "https://hooks.slack.com/services/TEST",
        }

        router = NotificationRouter(
            email_service=None,
            slack_service=mock_slack_service,
            webhook_service=None,
            config_repository=mock_config_repo,
        )

        recipient_id = uuid4()
        await router.send_notification(recipient_id, "Review required", test_review_item, tenant_id)

        # Verify Slack service was called
        mock_slack_service.send_notification.assert_awaited_once_with(
            recipient_id, "Review required", test_review_item, tenant_id
        )

    @pytest.mark.asyncio
    async def test_routes_to_webhook_when_webhook_enabled(self, test_review_item, tenant_id):
        """NotificationRouter should route to webhook service when webhook is enabled."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_webhook_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["webhook"],
            "webhook_url": "https://api.example.com/hitl",
        }

        router = NotificationRouter(
            email_service=None,
            slack_service=None,
            webhook_service=mock_webhook_service,
            config_repository=mock_config_repo,
        )

        recipient_id = uuid4()
        await router.send_notification(recipient_id, "Review required", test_review_item, tenant_id)

        # Verify webhook service was called
        mock_webhook_service.send_notification.assert_awaited_once_with(
            recipient_id, "Review required", test_review_item, tenant_id
        )

    @pytest.mark.asyncio
    async def test_routes_to_multiple_channels_when_all_enabled(self, test_review_item, tenant_id):
        """NotificationRouter should route to ALL enabled channels simultaneously."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_email_service = AsyncMock()
        mock_slack_service = AsyncMock()
        mock_webhook_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email", "slack", "webhook"],
            "email_recipients": ["pm@example.com"],
            "slack_webhook_url": "https://hooks.slack.com/services/TEST",
            "webhook_url": "https://api.example.com/hitl",
        }

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=mock_slack_service,
            webhook_service=mock_webhook_service,
            config_repository=mock_config_repo,
        )

        recipient_id = uuid4()
        message = "Review required"

        await router.send_notification(recipient_id, message, test_review_item, tenant_id)

        # Verify ALL services were called
        mock_email_service.send_notification.assert_awaited_once()
        mock_slack_service.send_notification.assert_awaited_once()
        mock_webhook_service.send_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_log_when_no_channels_configured(self, test_review_item, tenant_id):
        """NotificationRouter should fall back to LogNotificationService when no channels configured."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_log_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": [],
        }

        router = NotificationRouter(
            email_service=None,
            slack_service=None,
            webhook_service=None,
            config_repository=mock_config_repo,
            log_service=mock_log_service,
        )

        await router.send_notification(uuid4(), "Review required", test_review_item, tenant_id)

        # Verify log service was called as fallback
        mock_log_service.send_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_log_service_in_local_dev_environment(self, test_review_item, tenant_id):
        """NotificationRouter should use log-only in local dev (ENV=development)."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_log_service = AsyncMock()
        mock_email_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email"],
        }

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=None,
            webhook_service=None,
            config_repository=mock_config_repo,
            log_service=mock_log_service,
            environment="development",  # Local dev
        )

        await router.send_notification(uuid4(), "Review required", test_review_item, tenant_id)

        # In development, should use log service only
        mock_log_service.send_notification.assert_awaited_once()
        mock_email_service.send_notification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_continues_on_partial_failure(self, test_review_item, tenant_id):
        """If one channel fails, other channels should still be notified."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_email_service = AsyncMock()
        mock_email_service.send_notification.side_effect = Exception("SMTP failure")

        mock_slack_service = AsyncMock()  # Should succeed
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email", "slack"],
        }

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=mock_slack_service,
            webhook_service=None,
            config_repository=mock_config_repo,
        )

        # Should not raise exception - should log error and continue
        await router.send_notification(uuid4(), "Review required", test_review_item, tenant_id)

        # Verify email failed but Slack was still called
        mock_email_service.send_notification.assert_awaited_once()
        mock_slack_service.send_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_escalation_alert_routes_to_all_enabled_channels(self, test_review_item, tenant_id):
        """Escalation alerts should be sent to all enabled channels."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_email_service = AsyncMock()
        mock_slack_service = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email", "slack"],
        }

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=mock_slack_service,
            webhook_service=None,
            config_repository=mock_config_repo,
        )

        await router.send_escalation_alert(test_review_item, tenant_id)

        # Verify all enabled services received escalation
        mock_email_service.send_escalation_alert.assert_awaited_once()
        mock_slack_service.send_escalation_alert.assert_awaited_once()


class TestNotificationRouterIntegration:
    """Integration tests for NotificationRouter."""

    @pytest.mark.asyncio
    async def test_config_caching_avoids_repeated_lookups(self, test_review_item, tenant_id):
        """Config should be cached to avoid repeated database lookups."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email"],
        }
        mock_email_service = AsyncMock()

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=None,
            webhook_service=None,
            config_repository=mock_config_repo,
            cache_ttl_seconds=60,
        )

        # Send multiple notifications
        for _ in range(5):
            await router.send_notification(uuid4(), "Test", test_review_item, tenant_id)

        # Config should only be fetched once (cached)
        assert mock_config_repo.get_config.await_count == 1

    @pytest.mark.asyncio
    async def test_config_refresh_after_cache_expiry(self, test_review_item, tenant_id):
        """Config should be refreshed after cache TTL expires."""
        import asyncio

        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = {
            "notification_channels": ["email"],
        }
        mock_email_service = AsyncMock()

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=None,
            webhook_service=None,
            config_repository=mock_config_repo,
            cache_ttl_seconds=1,  # 1 second TTL
        )

        # Send notification
        await router.send_notification(uuid4(), "Test", test_review_item, tenant_id)
        assert mock_config_repo.get_config.await_count == 1

        # Wait for cache to expire
        await asyncio.sleep(1.1)

        # Send another notification
        await router.send_notification(uuid4(), "Test", test_review_item, tenant_id)

        # Config should be fetched again
        assert mock_config_repo.get_config.await_count == 2

    @pytest.mark.asyncio
    async def test_per_tenant_configuration_isolation(self, test_review_item):
        """Each tenant should have isolated notification configuration."""
        from src.modules.hitl.adapters.notifications.notification_router import (
            NotificationRouter,
        )

        tenant1 = uuid4()
        tenant2 = uuid4()

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.side_effect = lambda tid: {
            tenant1: {"notification_channels": ["email"]},
            tenant2: {"notification_channels": ["slack"]},
        }[tid]

        mock_email_service = AsyncMock()
        mock_slack_service = AsyncMock()

        router = NotificationRouter(
            email_service=mock_email_service,
            slack_service=mock_slack_service,
            webhook_service=None,
            config_repository=mock_config_repo,
        )

        # Tenant 1 should use email
        await router.send_notification(uuid4(), "Test", test_review_item, tenant1)
        mock_email_service.send_notification.assert_awaited_once()
        mock_slack_service.send_notification.assert_not_awaited()

        mock_email_service.reset_mock()
        mock_slack_service.reset_mock()

        # Tenant 2 should use Slack
        await router.send_notification(uuid4(), "Test", test_review_item, tenant2)
        mock_email_service.send_notification.assert_not_awaited()
        mock_slack_service.send_notification.assert_awaited_once()
