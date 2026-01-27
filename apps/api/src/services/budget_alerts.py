from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Iterable
from uuid import UUID

import redis.asyncio as redis
import structlog
from redis.exceptions import RedisError
from sqlalchemy import select

from src.config import settings
from src.core.database import get_raw_session
from src.core.auth.models import Tenant, User, UserRole

logger = structlog.get_logger()

ALERT_THRESHOLDS = (50, 75, 90, 100)


@dataclass(frozen=True)
class BudgetAlertPayload:
    level: str
    message: str
    current_spend: str
    limit: str
    timestamp: str


class BudgetMonitor:
    """
    Background service that monitors monthly AI spend and sends alerts.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis = self._build_redis(redis_url or settings.redis_url)

    async def run(self) -> None:
        if self._redis is None:
            logger.warning("budget_alerts_disabled", reason="redis_url_missing")
            return

        async with get_raw_session() as session:
            result = await session.execute(select(Tenant))
            tenants = list(result.scalars().all())

        for tenant in tenants:
            await self._process_tenant(tenant)

    async def _process_tenant(self, tenant: Tenant) -> None:
        if tenant.ai_budget_monthly <= 0:
            return

        if not self._is_current_month(tenant.ai_spend_last_reset):
            return

        current_spend = float(tenant.ai_spend_current or 0.0)
        usage_percent = (current_spend / tenant.ai_budget_monthly) * 100

        threshold = self._next_threshold(usage_percent, await self._get_last_alert_level(tenant))
        if threshold is None:
            return

        payload = self._build_payload(
            threshold=threshold,
            spend=current_spend,
            limit=tenant.ai_budget_monthly,
        )

        await self._notify(tenant, payload)
        await self._set_last_alert_level(tenant, threshold)

    def _build_payload(self, threshold: int, spend: float, limit: float) -> BudgetAlertPayload:
        level = self._level_from_threshold(threshold)
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return BudgetAlertPayload(
            level=level,
            message=f"Budget utilization reached {threshold}%",
            current_spend=f"${spend:.2f}",
            limit=f"${limit:.2f}",
            timestamp=timestamp,
        )

    async def _notify(self, tenant: Tenant, payload: BudgetAlertPayload) -> None:
        recipients = await self._get_admin_emails(tenant.id)
        if settings.budget_alert_admin_emails:
            recipients.extend(settings.budget_alert_admin_emails)

        recipients = sorted({email for email in recipients if email})
        if recipients:
            await self._send_email(tenant, recipients, payload)

        if settings.budget_alert_webhook_url:
            await self._send_webhook(payload)

    async def _get_admin_emails(self, tenant_id: UUID) -> list[str]:
        async with get_raw_session() as session:
            result = await session.execute(
                select(User.email).where(
                    User.tenant_id == tenant_id,
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
            return [row[0] for row in result.all() if row[0]]

    async def _send_email(
        self,
        tenant: Tenant,
        recipients: Iterable[str],
        payload: BudgetAlertPayload,
    ) -> None:
        if not settings.smtp_host:
            logger.warning("budget_alert_email_skipped", reason="smtp_host_missing")
            return

        subject = f"[C2Pro] Budget alert for {tenant.name}: {payload.message}"
        body = (
            f"Tenant: {tenant.name}\n"
            f"Level: {payload.level}\n"
            f"Message: {payload.message}\n"
            f"Current spend: {payload.current_spend}\n"
            f"Limit: {payload.limit}\n"
            f"Timestamp: {payload.timestamp}\n"
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_from or settings.email_from
        message["To"] = ", ".join(recipients)
        message.set_content(body)

        try:
            await asyncio.to_thread(self._send_smtp, message, recipients)
        except Exception as exc:
            logger.error("budget_alert_email_failed", error=str(exc), tenant_id=str(tenant.id))

    def _send_smtp(self, message: EmailMessage, recipients: Iterable[str]) -> None:
        import smtplib
        import ssl

        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls(context=context)
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message, from_addr=message["From"], to_addrs=list(recipients))

    async def _send_webhook(self, payload: BudgetAlertPayload) -> None:
        import httpx

        data = {
            "level": payload.level,
            "message": payload.message,
            "current_spend": payload.current_spend,
            "limit": payload.limit,
            "timestamp": payload.timestamp,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(settings.budget_alert_webhook_url, json=data)
        except Exception as exc:
            logger.warning("budget_alert_webhook_failed", error=str(exc))

    def _next_threshold(self, usage_percent: float, last_level: int) -> int | None:
        eligible = [t for t in ALERT_THRESHOLDS if usage_percent >= t and t > last_level]
        if eligible:
            return max(eligible)
        return None

    async def _get_last_alert_level(self, tenant: Tenant) -> int:
        if self._redis is None:
            return 0

        key = self._build_alert_key(tenant.id)
        try:
            value = await self._redis.get(key)
            return int(value) if value is not None else 0
        except RedisError as exc:
            logger.warning("budget_alert_cache_read_failed", error=str(exc))
            return 0

    async def _set_last_alert_level(self, tenant: Tenant, level: int) -> None:
        if self._redis is None:
            return

        key = self._build_alert_key(tenant.id)
        ttl_seconds = self._seconds_until_month_end()
        try:
            await self._redis.set(key, str(level), ex=ttl_seconds)
        except RedisError as exc:
            logger.warning("budget_alert_cache_write_failed", error=str(exc))

    def _build_alert_key(self, tenant_id: UUID) -> str:
        month_key = datetime.utcnow().strftime("%Y-%m")
        return f"budget_alert:{tenant_id}:{month_key}"

    def _seconds_until_month_end(self) -> int:
        now = datetime.utcnow()
        next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_of_month = next_month - timedelta(seconds=1)
        return max(3600, int((end_of_month - now).total_seconds()))

    def _level_from_threshold(self, threshold: int) -> str:
        if threshold >= 90:
            return "CRITICAL"
        if threshold >= 75:
            return "HIGH"
        return "MEDIUM"

    def _is_current_month(self, last_reset: datetime | None) -> bool:
        if last_reset is None:
            return False
        now = datetime.utcnow()
        return now.year == last_reset.year and now.month == last_reset.month

    def _build_redis(self, redis_url: str | None) -> redis.Redis | None:
        if not redis_url:
            return None
        try:
            return redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        except Exception as exc:
            logger.error("budget_alert_redis_init_failed", error=str(exc))
            return None
