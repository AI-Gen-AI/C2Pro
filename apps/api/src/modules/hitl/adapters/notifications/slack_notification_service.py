"""
SlackNotificationService - Slack webhook notifications.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Sends HITL notifications to Slack via incoming webhooks.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
import structlog

if TYPE_CHECKING:
    from src.modules.hitl.domain.entities import ReviewItem

logger = structlog.get_logger()


class SlackNotificationService:
    """Send HITL notifications to Slack via webhooks."""

    def __init__(
        self,
        webhook_url: str,
        max_retries: int = 3,
        timeout: float = 10.0,
    ):
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self.timeout = timeout

    async def send_notification(
        self, recipient_id: UUID, message: str, item: ReviewItem, tenant_id: UUID
    ) -> None:
        """Send notification to Slack channel."""
        _ = tenant_id
        payload = self._format_notification_payload(recipient_id, message, item)

        await self._post_to_slack(payload)

        logger.info(
            "slack_notification_sent",
            recipient_id=str(recipient_id),
            item_id=str(item.item_id),
        )

    async def send_escalation_alert(self, item: ReviewItem, tenant_id: UUID) -> None:
        """Send urgent escalation alert to Slack with @channel mention."""
        _ = tenant_id
        payload = self._format_escalation_payload(item)

        await self._post_to_slack(payload)

        logger.warning(
            "slack_escalation_sent",
            item_id=str(item.item_id),
            impact_level=item.impact_level.value,
        )

    async def _post_to_slack(self, payload: dict[str, Any]) -> None:
        """POST payload to Slack webhook with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(self.webhook_url, json=payload)

                    if response.status_code == 200:
                        logger.debug(
                            "slack_webhook_success",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        return

                    if response.status_code == 429:
                        # Rate limited
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(
                            "slack_rate_limited",
                            retry_after=retry_after,
                            attempt=attempt + 1,
                        )
                        raise Exception(f"Slack rate limited: retry after {retry_after}s")

                    # 4xx or 5xx errors
                    logger.error(
                        "slack_webhook_error",
                        status_code=response.status_code,
                        response=response.text,
                        attempt=attempt + 1,
                    )
                    raise Exception(
                        f"Slack webhook failed: {response.status_code} {response.text}"
                    )

            except httpx.TimeoutException as e:
                logger.warning(
                    "slack_timeout",
                    attempt=attempt + 1,
                    timeout=self.timeout,
                    error=str(e),
                )
                if attempt >= self.max_retries:
                    raise

            except Exception as e:
                logger.warning(
                    "slack_send_failed",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )

                if attempt >= self.max_retries:
                    logger.error(
                        "slack_send_failed_permanently",
                        attempts=attempt + 1,
                        error=str(e),
                    )
                    raise

            # Exponential backoff: 1s, 2s, 4s
            if attempt < self.max_retries:
                await asyncio.sleep(2**attempt)

    def _format_notification_payload(
        self, _recipient_id: UUID, message: str, item: ReviewItem
    ) -> dict[str, Any]:
        """Format Slack message payload with blocks."""
        document_name = item.item_data.get("document_name", "N/A")

        # Slack Block Kit format for rich messages
        payload = {
            "text": f"HITL Review Required: {item.item_type}",  # Fallback text
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔔 HITL Review Required",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{message}*",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Item ID:*\n{item.item_id}"},
                        {"type": "mrkdwn", "text": f"*Type:*\n{item.item_type}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Confidence:*\n{item.confidence:.2f}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Impact:*\n{item.impact_level.value}",
                        },
                        {"type": "mrkdwn", "text": f"*Document:*\n{document_name}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Status:*\n{item.current_status.value}",
                        },
                    ],
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Review in Dashboard"},
                            "url": f"https://app.c2pro.com/hitl/{item.item_id}",  # TODO: Make configurable
                            "style": "primary",
                        },
                    ],
                },
            ],
        }

        return payload

    def _format_escalation_payload(self, item: ReviewItem) -> dict[str, Any]:
        """Format urgent escalation payload with @channel mention."""
        document_name = item.item_data.get("document_name", "N/A")

        payload = {
            "text": f"<!channel> URGENT ESCALATION: {item.item_type}",  # @channel mention
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ URGENT ESCALATION - HITL Review Overdue",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "<!channel> A high-priority review item has exceeded its SLA and requires *immediate attention*.",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Item ID:*\n{item.item_id}"},
                        {"type": "mrkdwn", "text": f"*Type:*\n{item.item_type}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Impact:*\n:warning: *{item.impact_level.value}*",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Confidence:*\n{item.confidence:.2f}",
                        },
                        {"type": "mrkdwn", "text": f"*Document:*\n{document_name}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*SLA Due:*\n{item.sla_due_date.isoformat() if item.sla_due_date else 'N/A'}",
                        },
                    ],
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "⚡ Review Now"},
                            "url": f"https://app.c2pro.com/hitl/{item.item_id}",
                            "style": "danger",
                        },
                    ],
                },
            ],
        }

        return payload
