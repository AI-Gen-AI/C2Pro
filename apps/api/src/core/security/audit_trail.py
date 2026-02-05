"""
Audit trail core security service.

Refers to Suite ID: TS-UC-SEC-AUD-001.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4


_SENSITIVE_KEYS: set[str] = {"password", "token", "query", "secret"}


@dataclass(frozen=True)
class AuditEvent:
    """Refers to Suite ID: TS-UC-SEC-AUD-001."""

    event_id: UUID
    tenant_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    timestamp: datetime
    metadata: dict[str, str] = field(default_factory=dict)
    previous_hash: str | None = None
    event_hash: str = ""


class AuditTrail:
    """Refers to Suite ID: TS-UC-SEC-AUD-001."""

    def __init__(
        self,
        datetime_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._datetime_provider = datetime_provider or (lambda: datetime.now(timezone.utc))
        self._events: list[AuditEvent] = []

    def record(
        self,
        tenant_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_id: str = "system",
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not action:
            raise ValueError("action is required")

        cleaned_metadata = self._redact_metadata(metadata or {})
        previous_hash = self._events[-1].event_hash if self._events else None
        timestamp = self._datetime_provider()

        payload_for_hash = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timestamp.isoformat(),
            "metadata": cleaned_metadata,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(
            json.dumps(payload_for_hash, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        event = AuditEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=timestamp,
            metadata=cleaned_metadata,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )
        self._events.append(event)
        return event

    def query(
        self,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        events = list(self._events)
        if tenant_id is not None:
            events = [event for event in events if event.tenant_id == tenant_id]
        if actor_id is not None:
            events = [event for event in events if event.actor_id == actor_id]
        if action is not None:
            events = [event for event in events if event.action == action]
        if from_timestamp is not None:
            events = [event for event in events if event.timestamp >= from_timestamp]
        if to_timestamp is not None:
            events = [event for event in events if event.timestamp <= to_timestamp]
        if limit is not None:
            events = events[-limit:]
        return events

    def verify_integrity(self, events: list[AuditEvent] | None = None) -> bool:
        chain = events if events is not None else self._events
        if not chain:
            return True

        expected_previous_hash: str | None = None
        for event in chain:
            if event.previous_hash != expected_previous_hash:
                return False
            recalculated_hash = self._compute_hash(event, expected_previous_hash)
            if recalculated_hash != event.event_hash:
                return False
            expected_previous_hash = event.event_hash
        return True

    @staticmethod
    def _redact_metadata(metadata: dict[str, str]) -> dict[str, str]:
        redacted: dict[str, str] = {}
        for key, value in metadata.items():
            if key.lower() in _SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        return redacted

    @staticmethod
    def _compute_hash(event: AuditEvent, previous_hash: str | None) -> str:
        payload_for_hash = {
            "tenant_id": event.tenant_id,
            "actor_id": event.actor_id,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata,
            "previous_hash": previous_hash,
        }
        return hashlib.sha256(
            json.dumps(payload_for_hash, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
