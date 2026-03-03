"""
I11 HITL notification service port.
Test Suite ID: TS-I11-HITL-PORT-001
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.modules.hitl.domain.entities import ReviewItem


class INotificationService(Protocol):
    async def send_notification(
        self, recipient_id: UUID, message: str, item: ReviewItem
    ) -> None:
        ...

    async def send_escalation_alert(self, item: ReviewItem) -> None:
        ...
