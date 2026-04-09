"""
WebhookNotificationService - Generic webhook notifications.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Sends HITL notifications to generic webhook endpoints with signature verification.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
import structlog

if TYPE_CHECKING:
    from src.modules.hitl.domain.entities import ReviewItem

logger = structlog.get_logger()


class WebhookNotificationService:
    """Send HITL notifications to generic webhook endpoints."""

    def __init__(
        self,
        webhook_url: str,
        auth_token: str | None = None,
        signing_secret: str | None = None,
        custom_headers: dict[str, str] | None = None,
        max_retries: int = 3,
        timeout: float = 10.0,
        retry_backoff_factor: float = 2.0,
    ):
        self.webhook_url = webhook_url
        self.auth_token = auth_token
        self.signing_secret = signing_secret
        self.custom_headers = custom_headers or {}
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_backoff_factor = retry_backoff_factor

    async def send_notification(
        self, recipient_id: UUID, message: str, item: ReviewItem
    ) -> None:
        """Send notification to webhook endpoint."""
        payload = self._format_notification_payload(recipient_id, message, item)

        await self._post_to_webhook(payload)

        logger.info(
            "webhook_notification_sent",
            recipient_id=str(recipient_id),
            item_id=str(item.item_id),
            webhook_url=self.webhook_url,
        )

    async def send_escalation_alert(self, item: ReviewItem) -> None:
        """Send urgent escalation alert to webhook endpoint."""
        payload = self._format_escalation_payload(item)

        await self._post_to_webhook(payload)

        logger.warning(
            "webhook_escalation_sent",
            item_id=str(item.item_id),
            impact_level=item.impact_level.value,
            webhook_url=self.webhook_url,
        )

    async def _post_to_webhook(self, payload: dict[str, Any]) -> None:
        """POST payload to webhook with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                headers = self._build_headers(payload)

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.webhook_url, json=payload, headers=headers
                    )

                    if response.status_code == 200:
                        logger.debug(
                            "webhook_success",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        return

                    # 4xx errors - client errors, don't retry
                    if 400 <= response.status_code < 500:
                        logger.error(
                            "webhook_client_error",
                            status_code=response.status_code,
                            response=response.text,
                            attempt=attempt + 1,
                        )
                        raise Exception(
                            f"Webhook client error: {response.status_code} {response.text}"
                        )

                    # 5xx errors - server errors, retry
                    logger.warning(
                        "webhook_server_error",
                        status_code=response.status_code,
                        response=response.text,
                        attempt=attempt + 1,
                    )
                    raise Exception(
                        f"Webhook server error: {response.status_code} {response.text}"
                    )

            except httpx.TimeoutException as e:
                logger.warning(
                    "webhook_timeout",
                    attempt=attempt + 1,
                    timeout=self.timeout,
                    error=str(e),
                )
                if attempt >= self.max_retries:
                    raise

            except Exception as e:
                logger.warning(
                    "webhook_send_failed",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )

                if attempt >= self.max_retries:
                    logger.error(
                        "webhook_send_failed_permanently",
                        attempts=attempt + 1,
                        error=str(e),
                    )
                    raise

            # Exponential backoff: base^attempt (2^0=1s, 2^1=2s, 2^2=4s)
            if attempt < self.max_retries:
                delay = self.retry_backoff_factor**attempt
                await asyncio.sleep(delay)

    def _build_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """Build HTTP headers for webhook request."""
        headers = {"Content-Type": "application/json"}

        # Add authorization header if token is provided
        if self.auth_token:
            headers["Authorization"] = self.auth_token

        # Add custom headers
        headers.update(self.custom_headers)

        # Add signature header if signing secret is provided
        if self.signing_secret:
            signature = self._compute_signature(payload)
            headers["X-Webhook-Signature"] = signature

        return headers

    def _compute_signature(self, payload: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 signature for payload verification."""
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(
            self.signing_secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def _format_notification_payload(
        self, recipient_id: UUID, message: str, item: ReviewItem
    ) -> dict[str, Any]:
        """Format webhook notification payload."""
        return {
            "event_type": "hitl.notification",
            "recipient_id": str(recipient_id),
            "message": message,
            "review_item": {
                "item_id": str(item.item_id),
                "item_type": item.item_type,
                "current_status": item.current_status.value,
                "confidence": item.confidence,
                "impact_level": item.impact_level.value,
                "item_data": item.item_data,
                "sla_due_date": (
                    item.sla_due_date.isoformat() if item.sla_due_date else None
                ),
            },
        }

    def _format_escalation_payload(self, item: ReviewItem) -> dict[str, Any]:
        """Format urgent escalation payload."""
        return {
            "event_type": "hitl.escalation",
            "review_item": {
                "item_id": str(item.item_id),
                "item_type": item.item_type,
                "current_status": item.current_status.value,
                "confidence": item.confidence,
                "impact_level": item.impact_level.value,
                "item_data": item.item_data,
                "sla_due_date": (
                    item.sla_due_date.isoformat() if item.sla_due_date else None
                ),
            },
        }
