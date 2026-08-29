"""Port for ProjectEvent append-only repository (ADR-015 / TASK-V3-015-03).

LOCKED INVARIANT: implementations MUST NOT call session commit().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.temporal.domain.project_event import ProjectEvent


class IProjectEventRepository(ABC):
    @abstractmethod
    async def append(self, event: ProjectEvent) -> ProjectEvent:
        ...

    @abstractmethod
    async def get(self, event_id: UUID, tenant_id: UUID) -> ProjectEvent | None:
        """Exact tenant-scoped lookup of one event (snapshot lineage resolution)."""
        ...

    @abstractmethod
    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[ProjectEvent]:
        ...


__all__ = ["IProjectEventRepository"]
