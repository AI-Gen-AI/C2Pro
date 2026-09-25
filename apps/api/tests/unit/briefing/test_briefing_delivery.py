"""
Tests for Morning Briefing delivery (TASK-V3-021-02, ADR-021).

RED phase: written before implementation.
Scope: BriefingDeliveryPort protocol, BriefingFormatter pure function,
       DeliverBriefingUseCase.
Invariant: delivery is fire-and-forget; formatter never calls external services.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.briefing.domain.projection import HealthDelta, MorningBriefingProjection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PROJECT = uuid.uuid4()
_TENANT = uuid.uuid4()
_T0 = datetime(2026, 8, 11, 8, 0, 0, tzinfo=UTC)


def _projection(
    *,
    new_action_item_count: int = 3,
    overdue_review_count: int = 1,
    health_deltas: tuple[HealthDelta, ...] = (),
    trigger_events: tuple[str, ...] = ("graph_completed",),
) -> MorningBriefingProjection:
    sid = uuid.uuid4()
    return MorningBriefingProjection(
        project_id=_PROJECT,
        snapshot_from_id=uuid.uuid4(),
        snapshot_to_id=sid,
        period_start=_T0,
        period_end=_T0,
        generated_at=_T0,
        health_deltas=health_deltas,
        new_action_item_count=new_action_item_count,
        overdue_review_count=overdue_review_count,
        trigger_events=trigger_events,
        evidence_refs=(str(sid),),
    )


# ---------------------------------------------------------------------------
# BriefingFormatter
# ---------------------------------------------------------------------------


class TestBriefingFormatter:
    def test_format_text_contains_project_id(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection()
        text = BriefingFormatter.format_text(proj)
        assert str(_PROJECT) in text

    def test_format_text_includes_new_action_item_count(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection(new_action_item_count=7)
        text = BriefingFormatter.format_text(proj)
        assert "7" in text

    def test_format_text_includes_overdue_review_count(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection(overdue_review_count=4)
        text = BriefingFormatter.format_text(proj)
        assert "4" in text

    def test_format_text_includes_positive_health_delta(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection(
            health_deltas=(HealthDelta(dimension="overall", previous=0.6, current=0.8),)
        )
        text = BriefingFormatter.format_text(proj)
        assert "overall" in text.lower()

    def test_format_text_includes_trigger_events(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection(trigger_events=("hitl_correction", "graph_completed"))
        text = BriefingFormatter.format_text(proj)
        assert "hitl_correction" in text

    def test_format_text_zero_deltas_neutral_message(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection(new_action_item_count=0, overdue_review_count=0)
        text = BriefingFormatter.format_text(proj)
        assert text  # non-empty

    def test_format_returns_str(self) -> None:
        from src.briefing.application.briefing_formatter import BriefingFormatter

        proj = _projection()
        assert isinstance(BriefingFormatter.format_text(proj), str)


# ---------------------------------------------------------------------------
# BriefingDeliveryPort protocol
# ---------------------------------------------------------------------------


class TestBriefingDeliveryPort:
    def test_protocol_is_structurally_checkable(self) -> None:
        from src.briefing.ports.briefing_delivery_port import BriefingDeliveryPort

        class NoopDelivery:
            async def deliver(
                self,
                recipient: str,
                subject: str,
                body: str,
                *,
                channel: str = "email",
            ) -> None:
                pass

        assert isinstance(NoopDelivery(), BriefingDeliveryPort)

    def test_missing_deliver_fails_protocol_check(self) -> None:
        from src.briefing.ports.briefing_delivery_port import BriefingDeliveryPort

        class BadDelivery:
            pass

        assert not isinstance(BadDelivery(), BriefingDeliveryPort)


# ---------------------------------------------------------------------------
# DeliverBriefingUseCase
# ---------------------------------------------------------------------------


class TestDeliverBriefingUseCase:
    @pytest.mark.asyncio
    async def test_deliver_calls_port_with_formatted_body(self) -> None:
        from src.briefing.application.deliver_briefing_use_case import (
            DeliverBriefingCommand,
            DeliverBriefingUseCase,
        )

        port = AsyncMock()
        port.deliver = AsyncMock()
        uc = DeliverBriefingUseCase(delivery_port=port)

        proj = _projection(new_action_item_count=5)
        cmd = DeliverBriefingCommand(
            projection=proj,
            recipient="cm@example.com",
            channel="email",
        )
        await uc.execute(cmd)

        port.deliver.assert_awaited_once()
        _recipient, _subject, body = port.deliver.call_args.args
        assert "5" in body or "5" in _subject

    @pytest.mark.asyncio
    async def test_deliver_passes_recipient_and_channel(self) -> None:
        from src.briefing.application.deliver_briefing_use_case import (
            DeliverBriefingCommand,
            DeliverBriefingUseCase,
        )

        port = AsyncMock()
        port.deliver = AsyncMock()
        uc = DeliverBriefingUseCase(delivery_port=port)

        proj = _projection()
        cmd = DeliverBriefingCommand(
            projection=proj,
            recipient="slack-channel-id",
            channel="slack",
        )
        await uc.execute(cmd)

        call_kwargs = port.deliver.call_args.kwargs
        assert call_kwargs.get("channel") == "slack"
        args = port.deliver.call_args.args
        assert args[0] == "slack-channel-id"

    @pytest.mark.asyncio
    async def test_deliver_does_not_raise_on_port_success(self) -> None:
        from src.briefing.application.deliver_briefing_use_case import (
            DeliverBriefingCommand,
            DeliverBriefingUseCase,
        )

        port = AsyncMock()
        port.deliver = AsyncMock(return_value=None)
        uc = DeliverBriefingUseCase(delivery_port=port)

        proj = _projection()
        cmd = DeliverBriefingCommand(projection=proj, recipient="x@y.com", channel="email")
        await uc.execute(cmd)  # should not raise

    @pytest.mark.asyncio
    async def test_deliver_propagates_port_exception(self) -> None:
        from src.briefing.application.deliver_briefing_use_case import (
            DeliverBriefingCommand,
            DeliverBriefingUseCase,
        )

        port = AsyncMock()
        port.deliver = AsyncMock(side_effect=RuntimeError("SMTP down"))
        uc = DeliverBriefingUseCase(delivery_port=port)

        proj = _projection()
        cmd = DeliverBriefingCommand(projection=proj, recipient="x@y.com", channel="email")
        with pytest.raises(RuntimeError, match="SMTP down"):
            await uc.execute(cmd)
