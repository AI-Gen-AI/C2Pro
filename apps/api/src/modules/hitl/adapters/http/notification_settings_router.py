"""
Notification settings API endpoints.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, status

from src.core.security import CurrentTenantId, security_scheme
from src.modules.hitl.adapters.http.dependencies import (
    get_notification_config_repository,
)
from src.modules.hitl.adapters.http.notification_config_schemas import (
    NotificationConfigRequest,
    NotificationConfigResponse,
)
from src.modules.hitl.adapters.persistence.notification_config_repository import (
    NotificationConfigRepository,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/settings",
    tags=["HITL Settings"],
    dependencies=[Depends(security_scheme)],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/notifications",
    response_model=NotificationConfigResponse,
    summary="Get tenant notification configuration",
)
async def get_notification_config(
    tenant_id: CurrentTenantId,
    repo: NotificationConfigRepository = Depends(get_notification_config_repository),
) -> NotificationConfigResponse:
    """Get current notification configuration for the tenant."""
    config = await repo.get_config(tenant_id)

    # If no config found, return empty config (not 404)
    if not config or not config.get("notification_channels"):
        return NotificationConfigResponse(notification_channels=[])

    return NotificationConfigResponse.from_config(config)


@router.post(
    "/notifications",
    response_model=NotificationConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update notification configuration",
)
async def save_notification_config(
    payload: NotificationConfigRequest,
    tenant_id: CurrentTenantId,
    repo: NotificationConfigRepository = Depends(get_notification_config_repository),
) -> NotificationConfigResponse:
    """Create or update notification configuration for the tenant."""
    # Convert Pydantic model to dict for repository
    config_dict = {
        "notification_channels": [ch.value for ch in payload.notification_channels],
        "email_recipients": payload.email_recipients,
        "slack_webhook_url": str(payload.slack_webhook_url) if payload.slack_webhook_url else None,
        "webhook_url": str(payload.webhook_url) if payload.webhook_url else None,
        "webhook_auth_token": payload.webhook_auth_token,
        "custom_headers": payload.custom_headers,
    }

    await repo.save_config(tenant_id, config_dict)

    logger.info(
        "notification_config_updated",
        tenant_id=str(tenant_id),
        channels=config_dict["notification_channels"],
    )

    # Fetch the saved config to return
    saved_config = await repo.get_config(tenant_id)
    return NotificationConfigResponse.from_config(saved_config)
