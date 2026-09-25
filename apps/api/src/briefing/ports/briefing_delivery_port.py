"""Delivery port for morning briefing (ADR-021, TASK-V3-021-02)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BriefingDeliveryPort(Protocol):
    async def deliver(
        self,
        recipient: str,
        subject: str,
        body: str,
        *,
        channel: str = "email",
    ) -> None: ...


__all__ = ["BriefingDeliveryPort"]
