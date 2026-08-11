"""DeliverBriefingUseCase — format projection and dispatch via port (ADR-021)."""

from __future__ import annotations

from dataclasses import dataclass

from src.briefing.application.briefing_formatter import BriefingFormatter
from src.briefing.domain.projection import MorningBriefingProjection
from src.briefing.ports.briefing_delivery_port import BriefingDeliveryPort


@dataclass(frozen=True)
class DeliverBriefingCommand:
    projection: MorningBriefingProjection
    recipient: str
    channel: str = "email"


class DeliverBriefingUseCase:
    def __init__(self, delivery_port: BriefingDeliveryPort) -> None:
        self._port = delivery_port

    async def execute(self, command: DeliverBriefingCommand) -> None:
        subject = BriefingFormatter.format_subject(command.projection)
        body = BriefingFormatter.format_text(command.projection)
        await self._port.deliver(
            command.recipient,
            subject,
            body,
            channel=command.channel,
        )


__all__ = ["DeliverBriefingCommand", "DeliverBriefingUseCase"]
