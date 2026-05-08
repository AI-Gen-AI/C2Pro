"""
EmailNotificationService - SMTP-based email notifications.
Part of TASK-BCK-025: Add real notification delivery beyond log-only.

Sends HITL notifications via SMTP (SendGrid, AWS SES, or any SMTP server).
"""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

try:
    import aiosmtplib
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests/dev
    aiosmtplib = None

if TYPE_CHECKING:
    from src.modules.hitl.adapters.notifications.recipient_resolver import (
        RecipientResolver,
    )
    from src.modules.hitl.domain.entities import ReviewItem

logger = structlog.get_logger()


class EmailNotificationService:
    """Send HITL notifications via email using SMTP.

    Attributes:
        recipient_resolver: Maps recipient UUID → e-mail address. Required
            for real deployments; without it, ``send_notification`` refuses
            to send (avoiding the old "UUID-as-recipient" footgun).
        escalation_recipients: Static list of emails to fan escalation
            alerts out to. Falls back to ``from_email`` when empty.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        max_retries: int = 3,
        recipient_resolver: RecipientResolver | None = None,
        escalation_recipients: list[str] | None = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.max_retries = max_retries
        self.recipient_resolver = recipient_resolver
        self.escalation_recipients = list(escalation_recipients or [])

    async def send_notification(
        self, recipient_id: UUID, message: str, item: ReviewItem, tenant_id: UUID
    ) -> None:
        """Send notification email for review item."""
        _ = tenant_id  # tenant_id is handled by NotificationRouter or used for routing logic
        to_address = await self._resolve_recipient_email(recipient_id)
        if to_address is None:
            logger.warning(
                "email_notification_skipped_no_recipient_email",
                recipient_id=str(recipient_id),
                item_id=str(item.item_id),
            )
            return

        subject = f"HITL Review Required: {item.item_type}"
        body = self._format_notification_body(recipient_id, message, item)

        await self._send_email(
            to_address=to_address,
            subject=subject,
            body=body,
        )

        logger.info(
            "email_notification_sent",
            recipient_id=str(recipient_id),
            to=to_address,
            item_id=str(item.item_id),
            smtp_host=self.smtp_host,
        )

    async def send_escalation_alert(self, item: ReviewItem, tenant_id: UUID) -> None:
        """Send urgent escalation alert email to configured escalation list."""
        _ = tenant_id
        subject = f"URGENT ESCALATION: HITL Review Overdue - {item.item_type}"
        body = self._format_escalation_body(item)

        recipients = self.escalation_recipients or [self.from_email]
        for to_address in recipients:
            await self._send_email(
                to_address=to_address,
                subject=subject,
                body=body,
            )

        logger.warning(
            "email_escalation_sent",
            item_id=str(item.item_id),
            impact_level=item.impact_level.value,
            recipients=recipients,
            smtp_host=self.smtp_host,
        )

    async def _resolve_recipient_email(self, recipient_id: UUID) -> str | None:
        """Map a recipient UUID to an email via the configured resolver."""
        if self.recipient_resolver is None:
            logger.error(
                "email_notification_no_resolver_configured",
                recipient_id=str(recipient_id),
            )
            return None
        return await self.recipient_resolver.resolve_email(recipient_id)

    async def _send_email(self, to_address: str, subject: str, body: str) -> None:
        """Send email with retry logic."""
        if aiosmtplib is None:
            raise ModuleNotFoundError("aiosmtplib is required for SMTP email notifications")

        for attempt in range(self.max_retries + 1):
            try:
                message = EmailMessage()
                message["From"] = self.from_email
                message["To"] = to_address
                message["Subject"] = subject
                message.set_content(body)

                smtp = aiosmtplib.SMTP(hostname=self.smtp_host, port=self.smtp_port)
                await smtp.connect()

                if self.smtp_user and self.smtp_password:
                    await smtp.login(self.smtp_user, self.smtp_password)

                await smtp.send_message(message)
                await smtp.quit()

                logger.debug(
                    "email_sent_successfully",
                    to=to_address,
                    subject=subject,
                    attempt=attempt + 1,
                )
                return

            except Exception as e:
                logger.warning(
                    "email_send_failed",
                    to=to_address,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )

                if attempt >= self.max_retries:
                    logger.error(
                        "email_send_failed_permanently",
                        to=to_address,
                        attempts=attempt + 1,
                        error=str(e),
                    )
                    raise

                # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(2**attempt)

    def _format_notification_body(
        self, _recipient_id: UUID, message: str, item: ReviewItem
    ) -> str:
        """Format notification email body with review item details."""
        document_name = item.item_data.get("document_name", "N/A")
        stakeholders = item.item_data.get("stakeholders", [])

        body = f"""
HITL Review Required

{message}

Review Item Details:
-------------------
Item ID: {item.item_id}
Item Type: {item.item_type}
Status: {item.current_status.value}
Confidence: {item.confidence:.2f}
Impact Level: {item.impact_level.value}

Document: {document_name}
Stakeholders: {', '.join(stakeholders) if stakeholders else 'N/A'}

Action Required:
Please review this item in the HITL dashboard and approve or reject it.

---
This is an automated notification from C2PRO HITL System.
"""
        return body.strip()

    def _format_escalation_body(self, item: ReviewItem) -> str:
        """Format escalation alert email body."""
        document_name = item.item_data.get("document_name", "N/A")

        body = f"""
⚠️ URGENT ESCALATION - HITL REVIEW OVERDUE ⚠️

A high-priority review item has exceeded its SLA and requires immediate attention.

Review Item Details:
-------------------
Item ID: {item.item_id}
Item Type: {item.item_type}
Status: {item.current_status.value}
Impact Level: {item.impact_level.value} (HIGH PRIORITY)
Confidence: {item.confidence:.2f}
SLA Due Date: {item.sla_due_date.isoformat() if item.sla_due_date else 'N/A'}

Document: {document_name}

Immediate Action Required:
This item has been escalated due to SLA breach. Please review immediately.

---
This is an automated escalation from C2PRO HITL System.
"""
        return body.strip()
