"""
Audit trail core domain tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.core.security.audit_trail import AuditEvent, AuditTrail


class TestAuditTrailCore:
    """Refers to Suite ID: TS-UC-SEC-AUD-001"""

    def test_001_record_event_creates_audit_event(self) -> None:
        trail = AuditTrail()
        event = trail.record(
            tenant_id="tenant_a",
            action="mcp.operation_allowed",
            resource_type="mcp",
            resource_id="view_projects_summary",
        )
        assert isinstance(event, AuditEvent)

    def test_002_record_event_has_uuid(self) -> None:
        trail = AuditTrail()
        event = trail.record("tenant_a", "action", "resource", "id")
        assert isinstance(event.event_id, UUID)

    def test_003_record_event_has_utc_timestamp(self) -> None:
        trail = AuditTrail()
        event = trail.record("tenant_a", "action", "resource", "id")
        assert event.timestamp.tzinfo is not None

    def test_004_record_event_default_actor_system(self) -> None:
        trail = AuditTrail()
        event = trail.record("tenant_a", "action", "resource", "id")
        assert event.actor_id == "system"

    def test_005_record_event_requires_tenant_id(self) -> None:
        trail = AuditTrail()
        with pytest.raises(ValueError, match="tenant_id is required"):
            trail.record("", "action", "resource", "id")

    def test_006_record_event_requires_action(self) -> None:
        trail = AuditTrail()
        with pytest.raises(ValueError, match="action is required"):
            trail.record("tenant_a", "", "resource", "id")

    def test_007_sensitive_metadata_fields_are_redacted(self) -> None:
        trail = AuditTrail()
        event = trail.record(
            "tenant_a",
            "auth.login_failed",
            "user",
            "u1",
            metadata={"password": "secret", "token": "abc", "safe": "ok"},
        )
        assert event.metadata["password"] == "[REDACTED]"
        assert event.metadata["token"] == "[REDACTED]"
        assert event.metadata["safe"] == "ok"

    def test_008_query_by_tenant_filters_events(self) -> None:
        trail = AuditTrail()
        trail.record("tenant_a", "a", "r", "1")
        trail.record("tenant_b", "b", "r", "2")
        result = trail.query(tenant_id="tenant_a")
        assert len(result) == 1
        assert result[0].tenant_id == "tenant_a"

    def test_009_query_by_actor_filters_events(self) -> None:
        trail = AuditTrail()
        trail.record("tenant_a", "a", "r", "1", actor_id="u1")
        trail.record("tenant_a", "b", "r", "2", actor_id="u2")
        result = trail.query(actor_id="u2")
        assert len(result) == 1
        assert result[0].actor_id == "u2"

    def test_010_query_by_action_filters_events(self) -> None:
        trail = AuditTrail()
        trail.record("tenant_a", "x", "r", "1")
        trail.record("tenant_a", "y", "r", "2")
        result = trail.query(action="y")
        assert len(result) == 1
        assert result[0].action == "y"

    def test_011_query_by_time_range_filters_events(self) -> None:
        times = [
            datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 5, 10, 1, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 5, 10, 2, 0, tzinfo=timezone.utc),
        ]
        trail = AuditTrail(datetime_provider=lambda: times.pop(0))
        trail.record("tenant_a", "a1", "r", "1")
        trail.record("tenant_a", "a2", "r", "2")
        trail.record("tenant_a", "a3", "r", "3")
        result = trail.query(
            from_timestamp=datetime(2026, 2, 5, 10, 1, 0, tzinfo=timezone.utc),
            to_timestamp=datetime(2026, 2, 5, 10, 2, 0, tzinfo=timezone.utc),
        )
        assert [event.action for event in result] == ["a2", "a3"]

    def test_012_query_limit_returns_latest_n(self) -> None:
        trail = AuditTrail()
        trail.record("tenant_a", "a1", "r", "1")
        trail.record("tenant_a", "a2", "r", "2")
        trail.record("tenant_a", "a3", "r", "3")
        result = trail.query(limit=2)
        assert [event.action for event in result] == ["a2", "a3"]

    def test_013_events_returned_in_chronological_order(self) -> None:
        base = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        step = {"i": 0}

        def _clock() -> datetime:
            value = base + timedelta(seconds=step["i"])
            step["i"] += 1
            return value

        trail = AuditTrail(datetime_provider=_clock)
        trail.record("tenant_a", "a1", "r", "1")
        trail.record("tenant_a", "a2", "r", "2")
        events = trail.query()
        assert events[0].timestamp <= events[1].timestamp

    def test_014_chain_hash_populated(self) -> None:
        trail = AuditTrail()
        first = trail.record("tenant_a", "a1", "r", "1")
        second = trail.record("tenant_a", "a2", "r", "2")
        assert first.event_hash
        assert second.previous_hash == first.event_hash

    def test_015_verify_integrity_true_for_valid_chain(self) -> None:
        trail = AuditTrail()
        trail.record("tenant_a", "a1", "r", "1")
        trail.record("tenant_a", "a2", "r", "2")
        assert trail.verify_integrity() is True

    def test_016_verify_integrity_false_for_tampered_chain(self) -> None:
        trail = AuditTrail()
        event_1 = trail.record("tenant_a", "a1", "r", "1")
        event_2 = trail.record("tenant_a", "a2", "r", "2")
        tampered = AuditEvent(
            event_id=event_2.event_id,
            tenant_id=event_2.tenant_id,
            actor_id=event_2.actor_id,
            action="a2-tampered",
            resource_type=event_2.resource_type,
            resource_id=event_2.resource_id,
            timestamp=event_2.timestamp,
            metadata=event_2.metadata,
            previous_hash=event_1.event_hash,
            event_hash=event_2.event_hash,
        )
        assert trail.verify_integrity([event_1, tampered]) is False
