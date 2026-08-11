"""
Port: audit repository (ADR-020, TASK-V3-020-03).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.modules.hitl.domain.audit import AuditEntry


class IAuditRepository(Protocol):
    async def add_entry(self, entry: AuditEntry) -> None: ...

    async def list_by_queue_entry(self, queue_entry_id: UUID) -> list[AuditEntry]: ...

    async def get_entry(self, entry_id: UUID) -> AuditEntry | None: ...


__all__ = ["IAuditRepository"]
