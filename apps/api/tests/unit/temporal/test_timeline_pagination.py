"""TS-UT-P0C-TEMPORAL-002 - deterministic ProjectEvent timeline pagination."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.temporal.application.timeline import (
    InvalidTimelineCursor,
    TimelineScope,
    decode_cursor,
    encode_cursor,
    paginate_events,
)
from src.temporal.domain.project_event import ProjectEvent


def _event(
    event_id: UUID,
    occurred_at: datetime,
    *,
    project_id: UUID | None = None,
    tenant_id: UUID | None = None,
) -> ProjectEvent:
    return ProjectEvent(
        event_id=event_id,
        project_id=project_id or uuid4(),
        tenant_id=tenant_id or uuid4(),
        event_type="revision.ingested",
        payload={},
        occurred_at=occurred_at,
        created_at=occurred_at,
    )


def test_same_timestamp_events_have_a_repeatable_event_id_tiebreaker() -> None:
    """TS-UT-P0C-TEMPORAL-002: equal clocks cannot scramble the history."""
    occurred_at = datetime(2026, 9, 13, tzinfo=UTC)
    low_id = UUID("00000000-0000-0000-0000-000000000001")
    high_id = UUID("00000000-0000-0000-0000-000000000002")

    tenant_id, project_id = uuid4(), uuid4()
    scope = TimelineScope(tenant_id=tenant_id, project_id=project_id)
    secret = "test-cursor-secret"
    events = [
        _event(high_id, occurred_at, project_id=project_id, tenant_id=tenant_id),
        _event(low_id, occurred_at, project_id=project_id, tenant_id=tenant_id),
    ]
    page = paginate_events(events, limit=1, scope=scope, secret=secret)

    assert [event.event_id for event in page.items] == [low_id]
    assert page.next_cursor == encode_cursor(occurred_at, low_id, scope=scope, secret=secret)
    next_page = paginate_events(
        events,
        limit=1,
        cursor=page.next_cursor,
        scope=scope,
        secret=secret,
    )
    assert [event.event_id for event in next_page.items] == [high_id]
    assert next_page.next_cursor is None


def test_cursor_rejects_unrecognised_or_malformed_payloads() -> None:
    """TS-UT-P0C-TEMPORAL-002: stale cursors fail closed instead of restarting."""
    scope = TimelineScope(tenant_id=uuid4(), project_id=uuid4())
    with pytest.raises(InvalidTimelineCursor):
        decode_cursor("not-a-cursor", scope=scope, secret="test-cursor-secret")
    with pytest.raises(InvalidTimelineCursor):
        decode_cursor("eyJ2IjoyfQ", scope=scope, secret="test-cursor-secret")


def test_cursor_cannot_be_replayed_or_tampered_across_a_tenant_or_project() -> None:
    """TS-UT-P0C-TEMPORAL-002: opaque cursors bind the exact timeline scope."""
    secret = "test-cursor-secret"
    scope_a = TimelineScope(tenant_id=uuid4(), project_id=uuid4())
    cursor = encode_cursor(datetime(2026, 9, 13, tzinfo=UTC), uuid4(), scope=scope_a, secret=secret)

    with pytest.raises(InvalidTimelineCursor):
        decode_cursor(cursor, scope=TimelineScope(tenant_id=scope_a.tenant_id, project_id=uuid4()), secret=secret)
    with pytest.raises(InvalidTimelineCursor):
        decode_cursor(cursor[:-1] + ("A" if cursor[-1] != "A" else "B"), scope=scope_a, secret=secret)
