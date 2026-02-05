"""
TS-UC-SEC-MCP-004: MCP Gateway audit adapter.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class MCPAuditEventType(str, Enum):
    """Refers to Suite ID: TS-UC-SEC-MCP-004."""

    OPERATION_ALLOWED = "mcp.operation_allowed"
    OPERATION_BLOCKED = "mcp.operation_blocked"


@dataclass(frozen=True)
class MCPAuditEvent:
    """Refers to Suite ID: TS-UC-SEC-MCP-004."""

    tenant_id: str
    operation_name: str
    event_type: MCPAuditEventType
    timestamp: datetime
    reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class MCPAuditLogger:
    """Refers to Suite ID: TS-UC-SEC-MCP-004."""

    def __init__(
        self,
        datetime_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._datetime_provider = datetime_provider or (lambda: datetime.now(timezone.utc))
        self._events: list[MCPAuditEvent] = []
        self._lock = asyncio.Lock()

    async def log_operation_allowed(
        self,
        tenant_id: str,
        operation_name: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        await self._append_event(
            tenant_id=tenant_id,
            operation_name=operation_name,
            event_type=MCPAuditEventType.OPERATION_ALLOWED,
            reason=None,
            metadata=metadata or {},
        )

    async def log_operation_blocked(
        self,
        tenant_id: str,
        operation_name: str,
        reason: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        await self._append_event(
            tenant_id=tenant_id,
            operation_name=operation_name,
            event_type=MCPAuditEventType.OPERATION_BLOCKED,
            reason=reason,
            metadata=metadata or {},
        )

    async def list_events(
        self,
        tenant_id: str | None = None,
        limit: int | None = None,
    ) -> list[MCPAuditEvent]:
        async with self._lock:
            events = self._events
            if tenant_id:
                events = [event for event in events if event.tenant_id == tenant_id]
            if limit is not None:
                events = events[-limit:]
            return list(events)

    async def _append_event(
        self,
        tenant_id: str,
        operation_name: str,
        event_type: MCPAuditEventType,
        reason: str | None,
        metadata: dict[str, str],
    ) -> None:
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty or None")
        if not operation_name:
            raise ValueError("Operation name cannot be empty or None")

        normalized_operation = operation_name.strip().lower()
        cleaned_metadata = dict(metadata)
        if "query" in cleaned_metadata:
            cleaned_metadata["query"] = "[REDACTED]"

        event = MCPAuditEvent(
            tenant_id=tenant_id,
            operation_name=normalized_operation,
            event_type=event_type,
            timestamp=self._datetime_provider(),
            reason=reason,
            metadata=cleaned_metadata,
        )
        async with self._lock:
            self._events.append(event)
