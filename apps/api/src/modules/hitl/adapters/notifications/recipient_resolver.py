"""Recipient contact resolution for HITL notifications.

The HITL notification services accept a ``recipient_id`` (UUID) but need
an actual e-mail / handle to send to. This module defines the
``RecipientResolver`` protocol and a production implementation that
looks up the user's email via ``src.core.auth.service.get_user_by_id``.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


class RecipientResolver(Protocol):
    """Map a recipient UUID to a destination contact (email, handle, etc.)."""

    async def resolve_email(self, recipient_id: UUID) -> str | None: ...


class DbRecipientResolver:
    """Production resolver backed by the ``users`` table.

    The resolver keeps its own session factory so notification services
    can stay free of application-scoped sessions. Lookup failures return
    ``None`` so callers can log/fall-back instead of raising.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_email(self, recipient_id: UUID) -> str | None:
        from src.core.auth.service import get_user_by_id

        try:
            async with self._session_factory() as session:
                user = await get_user_by_id(session, recipient_id)
        except Exception as exc:  # noqa: BLE001 — resolver must be safe
            logger.warning(
                "recipient_resolver_lookup_failed",
                recipient_id=str(recipient_id),
                error=str(exc),
            )
            return None

        if user is None or not getattr(user, "email", None):
            logger.warning(
                "recipient_resolver_no_email",
                recipient_id=str(recipient_id),
            )
            return None
        return str(user.email)


class StaticRecipientResolver:
    """In-memory resolver for tests / dev — maps UUID → email directly."""

    def __init__(self, mapping: dict[UUID, str]) -> None:
        self._mapping = dict(mapping)

    async def resolve_email(self, recipient_id: UUID) -> str | None:
        return self._mapping.get(recipient_id)
