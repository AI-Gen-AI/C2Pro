"""
NotificationRouter - Strategy pattern for multi-channel notifications.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Routes notifications to enabled channels based on per-tenant configuration.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from src.modules.hitl.adapters.notifications.email_notification_service import (
        EmailNotificationService,
    )
    from src.modules.hitl.adapters.notifications.log_notification_service import (
        LogNotificationService,
    )
    from src.modules.hitl.adapters.notifications.slack_notification_service import (
        SlackNotificationService,
    )
    from src.modules.hitl.adapters.notifications.webhook_notification_service import (
        WebhookNotificationService,
    )
    from src.modules.hitl.domain.entities import ReviewItem

logger = structlog.get_logger()


class NotificationRouter:
    """Route notifications to enabled channels based on configuration."""

    def __init__(
        self,
        email_service: EmailNotificationService | None,
        slack_service: SlackNotificationService | None,
        webhook_service: WebhookNotificationService | None,
        config_repository: Any,  # NotificationConfigRepository
        log_service: LogNotificationService | None = None,
        environment: str = "production",
        cache_ttl_seconds: int = 300,
    ):
        self.email_service = email_service
        self.slack_service = slack_service
        self.webhook_service = webhook_service
        self.config_repository = config_repository
        self.log_service = log_service
        self.environment = environment
        self.cache_ttl_seconds = cache_ttl_seconds

        # Per-tenant config cache: {tenant_id: (config_dict, timestamp)}
        self._config_cache: dict[UUID, tuple[dict[str, Any], float]] = {}

    async def send_notification(
        self, recipient_id: UUID, message: str, item: ReviewItem, tenant_id: UUID
    ) -> None:
        """Send notification to all enabled channels for the tenant."""
        # In development, use log-only
        if self.environment == "development":
            if self.log_service:
                await self.log_service.send_notification(recipient_id, message, item, tenant_id)
            return

        # Get tenant configuration
        config = await self._get_config(tenant_id)
        channels = config.get("notification_channels", [])

        # If no channels configured, fall back to log-only
        if not channels:
            if self.log_service:
                await self.log_service.send_notification(recipient_id, message, item, tenant_id)
                logger.info(
                    "notification_fallback_to_log",
                    tenant_id=str(tenant_id),
                    reason="no_channels_configured",
                )
            return

        # Route to enabled channels (continue on partial failure)
        tasks = []

        if "email" in channels and self.email_service:
            tasks.append(
                self._send_with_error_handling(
                    "email",
                    self.email_service.send_notification(recipient_id, message, item, tenant_id),
                    tenant_id,
                )
            )

        if "slack" in channels and self.slack_service:
            tasks.append(
                self._send_with_error_handling(
                    "slack",
                    self.slack_service.send_notification(recipient_id, message, item, tenant_id),
                    tenant_id,
                )
            )

        if "webhook" in channels and self.webhook_service:
            tasks.append(
                self._send_with_error_handling(
                    "webhook",
                    self.webhook_service.send_notification(recipient_id, message, item, tenant_id),
                    tenant_id,
                )
            )

        # Execute all channels concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_escalation_alert(self, item: ReviewItem, tenant_id: UUID) -> None:
        """Send escalation alert to all enabled channels for the tenant."""
        # Get tenant configuration
        config = await self._get_config(tenant_id)
        channels = config.get("notification_channels", [])

        # Route to enabled channels (continue on partial failure)
        tasks = []

        if "email" in channels and self.email_service:
            tasks.append(
                self._send_with_error_handling(
                    "email",
                    self.email_service.send_escalation_alert(item, tenant_id),
                    tenant_id,
                )
            )

        if "slack" in channels and self.slack_service:
            tasks.append(
                self._send_with_error_handling(
                    "slack",
                    self.slack_service.send_escalation_alert(item, tenant_id),
                    tenant_id,
                )
            )

        if "webhook" in channels and self.webhook_service:
            tasks.append(
                self._send_with_error_handling(
                    "webhook",
                    self.webhook_service.send_escalation_alert(item, tenant_id),
                    tenant_id,
                )
            )

        # Execute all channels concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_with_error_handling(
        self, channel: str, coro: Any, tenant_id: UUID
    ) -> None:
        """Send notification with error handling - continue on failure."""
        try:
            await coro
        except Exception as e:
            logger.error(
                "notification_channel_failed",
                channel=channel,
                tenant_id=str(tenant_id),
                error=str(e),
            )
            # Don't re-raise - continue with other channels

    async def _get_config(self, tenant_id: UUID) -> dict[str, Any]:
        """Get tenant configuration with caching."""
        now = time.time()

        # Check cache
        if tenant_id in self._config_cache:
            cached_config, cached_time = self._config_cache[tenant_id]
            if now - cached_time < self.cache_ttl_seconds:
                return cached_config

        # Fetch from repository
        config = await self.config_repository.get_config(tenant_id)

        # Cache the result
        self._config_cache[tenant_id] = (config, now)

        return cast(dict[str, Any], config)
