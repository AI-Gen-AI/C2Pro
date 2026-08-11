"""
In-memory audit repository (ADR-020, TASK-V3-020-03).
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from src.modules.hitl.domain.audit import AuditEntry


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._by_queue: dict[UUID, list[AuditEntry]] = defaultdict(list)
        self._by_id: dict[UUID, AuditEntry] = {}

    async def add_entry(self, entry: AuditEntry) -> None:
        self._by_queue[entry.queue_entry_id].append(entry)
        self._by_id[entry.entry_id] = entry

    async def list_by_queue_entry(self, queue_entry_id: UUID) -> list[AuditEntry]:
        return list(self._by_queue.get(queue_entry_id, []))

    async def get_entry(self, entry_id: UUID) -> AuditEntry | None:
        return self._by_id.get(entry_id)


__all__ = ["InMemoryAuditRepository"]
