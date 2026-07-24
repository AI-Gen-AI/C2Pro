"""TS-UC-SEC-GAM-001: AbuseMonitorService process_event dispatch branch coverage."""

from __future__ import annotations

from typing import Any, NamedTuple
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.gamification.application.abuse_monitor_service import (
    AbuseMonitorService,
    AbuseType,
    AlertingService,
    AuditService,
    GamificationAbuseRepository,
    PenaltyService,
    WeightChangeEvent,
)

TENANT_A: UUID = uuid4()


@pytest.fixture
def mock_abuse_repo() -> MagicMock:
    repo = MagicMock(spec=GamificationAbuseRepository)
    repo.get_change_events_in_last_hour = AsyncMock(return_value=[])
    repo.get_resolution_count_for_hash = AsyncMock(return_value=0)
    repo.get_user_document_count = AsyncMock(return_value=100)
    repo.get_previous_weight_in_last_24h = AsyncMock(return_value=None)
    repo.log_change_event = AsyncMock()
    return repo


@pytest.fixture
def mock_alerting_service() -> MagicMock:
    return AsyncMock(spec=AlertingService)


@pytest.fixture
def mock_audit_service() -> MagicMock:
    return AsyncMock(spec=AuditService)


@pytest.fixture
def mock_penalty_service() -> MagicMock:
    return AsyncMock(spec=PenaltyService)


@pytest.fixture
def service(
    mock_abuse_repo: MagicMock,
    mock_alerting_service: MagicMock,
    mock_audit_service: MagicMock,
    mock_penalty_service: MagicMock,
) -> AbuseMonitorService:
    return AbuseMonitorService(
        repo=mock_abuse_repo,
        alerting_service=mock_alerting_service,
        audit_service=mock_audit_service,
        penalty_service=mock_penalty_service,
    )


@pytest.mark.asyncio
async def test_process_event_dispatches_to_resolution(
    service: AbuseMonitorService,
    mock_abuse_repo: MagicMock,
    mock_alerting_service: MagicMock,
) -> None:
    """Event with issue_hash (no component_id, no new_score) → process_issue_resolution_event."""
    mock_abuse_repo.get_resolution_count_for_hash.return_value = 2

    class ResolutionLike(NamedTuple):
        user_id: str
        tenant_id: UUID
        issue_hash: str

    event: Any = ResolutionLike(user_id="u1", tenant_id=TENANT_A, issue_hash="hash-abc")

    await service.process_event(event)

    mock_alerting_service.trigger_alert.assert_called_once()
    call_args = mock_alerting_service.trigger_alert.call_args
    assert call_args.kwargs["tenant_id"] == TENANT_A
    assert call_args.args[1] == AbuseType.RESOLVE_REINTRODUCE


@pytest.mark.asyncio
async def test_process_event_dispatches_to_score(
    service: AbuseMonitorService,
    mock_abuse_repo: MagicMock,
    mock_alerting_service: MagicMock,
) -> None:
    """Event with new_score (no component_id, no issue_hash) → process_score_update_event."""
    mock_abuse_repo.get_user_document_count.return_value = 2

    class ScoreLike(NamedTuple):
        user_id: str
        tenant_id: UUID
        new_score: float

    event: Any = ScoreLike(user_id="u1", tenant_id=TENANT_A, new_score=95.0)

    await service.process_event(event)

    mock_alerting_service.trigger_alert.assert_called_once()
    call_args = mock_alerting_service.trigger_alert.call_args
    assert call_args.args[1] == AbuseType.HIGH_SCORE_LOW_DOCS


@pytest.mark.asyncio
async def test_process_event_dispatches_to_change(
    service: AbuseMonitorService,
    mock_abuse_repo: MagicMock,
) -> None:
    """Event with user_id only (no component_id, issue_hash, new_score) → process_change_event."""
    mock_abuse_repo.get_change_events_in_last_hour.return_value = [
        object() for _ in range(5)
    ]

    class UserLike(NamedTuple):
        user_id: str
        tenant_id: UUID
        timestamp: float

    event: Any = UserLike(user_id="u1", tenant_id=TENANT_A, timestamp=1000.0)

    await service.process_event(event)

    mock_abuse_repo.log_change_event.assert_called_once_with(event)
    mock_abuse_repo.get_change_events_in_last_hour.assert_called_once_with(
        "u1", tenant_id=TENANT_A
    )


@pytest.mark.asyncio
async def test_weight_change_old_weight_none_skips(
    service: AbuseMonitorService,
    mock_abuse_repo: MagicMock,
    mock_alerting_service: MagicMock,
) -> None:
    """WeightChangeEvent with old_weight=None → guard false, no violation triggered."""
    mock_abuse_repo.get_previous_weight_in_last_24h.return_value = None

    event = WeightChangeEvent(
        user_id="u1",
        tenant_id=TENANT_A,
        component_id="comp-x",
        new_weight=500.0,
    )

    await service.process_weight_change_event(event)

    mock_alerting_service.trigger_alert.assert_not_called()
