"""Tests for the HITL recipient resolver and email service wiring."""

from __future__ import annotations

from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.modules.hitl.adapters.notifications.email_notification_service import (
    EmailNotificationService,
)
from src.modules.hitl.adapters.notifications.recipient_resolver import (
    DbRecipientResolver,
    StaticRecipientResolver,
)


class _FakeSession:
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


def _make_session_factory() -> Any:
    return lambda: _FakeSession()


@pytest.mark.asyncio
class TestStaticRecipientResolver:
    async def test_known_id_resolves_to_email(self) -> None:
        rid = uuid4()
        resolver = StaticRecipientResolver({rid: "user@example.com"})
        assert await resolver.resolve_email(rid) == "user@example.com"

    async def test_unknown_id_returns_none(self) -> None:
        resolver = StaticRecipientResolver({uuid4(): "x@example.com"})
        assert await resolver.resolve_email(uuid4()) is None


@pytest.mark.asyncio
class TestDbRecipientResolver:
    async def test_resolves_via_get_user_by_id(self) -> None:
        rid = uuid4()
        fake_user = type("U", (), {"email": "real@example.com"})()

        resolver = DbRecipientResolver(session_factory=_make_session_factory())
        with patch(
            "src.core.auth.service.get_user_by_id",
            new=AsyncMock(return_value=fake_user),
        ):
            assert await resolver.resolve_email(rid) == "real@example.com"

    async def test_returns_none_when_user_missing(self) -> None:
        resolver = DbRecipientResolver(session_factory=_make_session_factory())
        with patch(
            "src.core.auth.service.get_user_by_id",
            new=AsyncMock(return_value=None),
        ):
            assert await resolver.resolve_email(uuid4()) is None

    async def test_returns_none_when_user_has_no_email(self) -> None:
        fake_user = type("U", (), {"email": ""})()

        resolver = DbRecipientResolver(session_factory=_make_session_factory())
        with patch(
            "src.core.auth.service.get_user_by_id",
            new=AsyncMock(return_value=fake_user),
        ):
            assert await resolver.resolve_email(uuid4()) is None

    async def test_swallows_db_errors(self) -> None:
        resolver = DbRecipientResolver(session_factory=_make_session_factory())
        with patch(
            "src.core.auth.service.get_user_by_id",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            assert await resolver.resolve_email(uuid4()) is None


@pytest.mark.asyncio
class TestEmailNotificationServiceRecipientWiring:
    def _service(self, resolver, **overrides: Any) -> EmailNotificationService:
        kwargs = dict(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="noreply@example.com",
            smtp_password="pw",
            from_email="noreply@example.com",
            recipient_resolver=resolver,
        )
        kwargs.update(overrides)
        return EmailNotificationService(**kwargs)

    def _review_item(self, **overrides: Any):
        from datetime import datetime, timedelta, timezone

        from src.modules.hitl.domain.entities import (
            ImpactLevel,
            ReviewItem,
            ReviewStatus,
        )

        kwargs: dict[str, Any] = dict(
            item_id=uuid4(),
            item_type="risk",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.7,
            impact_level=ImpactLevel.MEDIUM,
            sla_due_date=datetime.now(UTC) + timedelta(hours=24),
            item_data={},
        )
        kwargs.update(overrides)
        return ReviewItem(**kwargs)

    async def test_skips_send_when_no_resolver_configured(self) -> None:
        service = self._service(resolver=None)
        sent: list[dict[str, str]] = []

        async def _spy(to_address: str, subject: str, body: str) -> None:
            sent.append({"to": to_address, "subject": subject})

        service._send_email = _spy  # type: ignore[assignment]

        await service.send_notification(uuid4(), "please review", self._review_item())
        assert sent == []

    async def test_sends_to_resolved_email(self) -> None:
        rid = uuid4()
        resolver = StaticRecipientResolver({rid: "team@example.com"})
        service = self._service(resolver=resolver)

        captured: dict[str, str] = {}

        async def _spy(to_address: str, subject: str, body: str) -> None:
            captured["to"] = to_address
            captured["subject"] = subject

        service._send_email = _spy  # type: ignore[assignment]

        await service.send_notification(
            rid,
            "please review",
            self._review_item(item_data={"document_name": "contract.pdf"}),
        )
        assert captured["to"] == "team@example.com"
        assert "HITL Review Required" in captured["subject"]

    async def test_escalation_uses_configured_recipients(self) -> None:
        resolver = StaticRecipientResolver({})
        service = self._service(
            resolver=resolver,
            escalation_recipients=["ops@example.com", "lead@example.com"],
        )

        sent_to: list[str] = []

        async def _spy(to_address: str, subject: str, body: str) -> None:
            sent_to.append(to_address)

        service._send_email = _spy  # type: ignore[assignment]

        from src.modules.hitl.domain.entities import ImpactLevel

        await service.send_escalation_alert(
            self._review_item(impact_level=ImpactLevel.HIGH, confidence=0.4)
        )
        assert sent_to == ["ops@example.com", "lead@example.com"]
