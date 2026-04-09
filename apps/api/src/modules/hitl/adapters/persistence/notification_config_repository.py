"""
NotificationConfigRepository - Persistence for tenant notification configuration.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.models import NotificationConfigModel

logger = structlog.get_logger()


class NotificationConfigRepository:
    """Repository for notification configuration CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config(self, tenant_id: UUID) -> dict[str, Any]:
        """Get notification configuration for a tenant."""
        stmt = select(NotificationConfigModel).where(
            NotificationConfigModel.tenant_id == tenant_id
        )
        result = await self.session.execute(stmt)
        config_model = result.scalar_one_or_none()

        if not config_model:
            # Return empty config if not found
            return {"notification_channels": []}

        return {
            "notification_channels": config_model.notification_channels or [],
            "email_recipients": config_model.email_recipients or [],
            "slack_webhook_url": config_model.slack_webhook_url,
            "webhook_url": config_model.webhook_url,
            "webhook_auth_token": config_model.webhook_auth_token,
            "custom_headers": config_model.custom_headers or {},
        }

    async def save_config(self, tenant_id: UUID, config: dict[str, Any]) -> None:
        """Save or update notification configuration for a tenant."""
        stmt = select(NotificationConfigModel).where(
            NotificationConfigModel.tenant_id == tenant_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing configuration
            existing.notification_channels = config.get("notification_channels", [])
            existing.email_recipients = config.get("email_recipients")
            existing.slack_webhook_url = config.get("slack_webhook_url")
            existing.webhook_url = config.get("webhook_url")
            existing.webhook_auth_token = config.get("webhook_auth_token")
            existing.custom_headers = config.get("custom_headers")
        else:
            # Create new configuration
            new_config = NotificationConfigModel(
                tenant_id=tenant_id,
                notification_channels=config.get("notification_channels", []),
                email_recipients=config.get("email_recipients"),
                slack_webhook_url=config.get("slack_webhook_url"),
                webhook_url=config.get("webhook_url"),
                webhook_auth_token=config.get("webhook_auth_token"),
                custom_headers=config.get("custom_headers"),
            )
            self.session.add(new_config)

        await self.session.commit()

        logger.info(
            "notification_config_saved",
            tenant_id=str(tenant_id),
            channels=config.get("notification_channels", []),
        )
