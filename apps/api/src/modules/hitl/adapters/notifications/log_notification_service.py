"""Log-based implementation of the NotificationService port.

Logs all notifications via structlog. Replace with email/Slack adapter
when external integrations are available.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.modules.hitl.application.ports import NotificationService
from src.modules.hitl.domain.entities import ReviewItem

logger = structlog.get_logger()


class LogNotificationService(NotificationService):
    async def send_notification(
        self, recipient_id: UUID, message: str, item: ReviewItem, tenant_id: UUID | None = None
    ) -> None:
        logger.info(
            "hitl_notification_sent",
            tenant_id=str(tenant_id) if tenant_id else "unknown",
            recipient_id=str(recipient_id),
            item_id=str(item.item_id),
            item_type=item.item_type,
            status=item.current_status.value,
            message=message,
        )

    async def send_escalation_alert(self, item: ReviewItem, tenant_id: UUID | None = None) -> None:
        logger.warning(
            "hitl_sla_escalation",
            tenant_id=str(tenant_id) if tenant_id else "unknown",
            item_id=str(item.item_id),
            item_type=item.item_type,
            sla_due_date=item.sla_due_date.isoformat(),
            impact_level=item.impact_level.value,
            confidence=item.confidence,
        )
