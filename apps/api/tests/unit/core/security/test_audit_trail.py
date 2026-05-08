"""Audit trail unit coverage.

Test Suite ID: TASK-OPS-DOCFLOW-013
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.core.security.audit_trail import AuditTrail


def test_audit_trail_records_redacted_hash_chained_events() -> None:
    """TASK-OPS-DOCFLOW-013: audit events redact sensitive data and form a chain."""
    timestamps = iter(
        [
            datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
            datetime(2026, 5, 7, 12, 5, tzinfo=UTC),
        ]
    )
    trail = AuditTrail(datetime_provider=lambda: next(timestamps))

    created = trail.record(
        tenant_id="tenant-a",
        actor_id="user-a",
        action="create",
        resource_type="document",
        resource_id="doc-1",
        metadata={"token": "secret", "status": "uploaded"},
    )
    updated = trail.record(
        tenant_id="tenant-a",
        actor_id="user-a",
        action="update",
        resource_type="document",
        resource_id="doc-1",
        metadata={"query": "raw search", "status": "processed"},
    )

    assert created.metadata == {"token": "[REDACTED]", "status": "uploaded"}
    assert updated.metadata == {"query": "[REDACTED]", "status": "processed"}
    assert updated.previous_hash == created.event_hash
    assert trail.verify_integrity() is True


def test_audit_trail_query_filters_by_tenant_actor_action_time_and_limit() -> None:
    """TASK-OPS-DOCFLOW-013: audit queries stay tenant and actor scoped."""
    current = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)

    def now() -> datetime:
        nonlocal current
        value = current
        current += timedelta(minutes=1)
        return value

    trail = AuditTrail(datetime_provider=now)
    trail.record("tenant-a", "create", "document", "doc-1", actor_id="user-a")
    expected = trail.record("tenant-a", "update", "document", "doc-1", actor_id="user-a")
    trail.record("tenant-b", "update", "document", "doc-2", actor_id="user-b")

    matches = trail.query(
        tenant_id="tenant-a",
        actor_id="user-a",
        action="update",
        from_timestamp=datetime(2026, 5, 7, 12, 1, tzinfo=UTC),
        to_timestamp=datetime(2026, 5, 7, 12, 2, tzinfo=UTC),
        limit=1,
    )

    assert matches == [expected]


def test_audit_trail_rejects_missing_required_fields_and_tampering() -> None:
    """TASK-OPS-DOCFLOW-013: required fields and hash integrity are enforced."""
    trail = AuditTrail(datetime_provider=lambda: datetime(2026, 5, 7, tzinfo=UTC))

    with pytest.raises(ValueError, match="tenant_id"):
        trail.record("", "create", "document", "doc-1")
    with pytest.raises(ValueError, match="action"):
        trail.record("tenant-a", "", "document", "doc-1")

    event = trail.record("tenant-a", "create", "document", "doc-1")
    tampered = replace(event, metadata={"status": "tampered"})

    assert trail.verify_integrity([tampered]) is False
    assert trail.verify_integrity([]) is True
