"""Port for ProjectEvent append-only repository (ADR-015 / TASK-V3-015-03).

LOCKED INVARIANT: implementations MUST NOT call session commit().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.temporal.application.timeline import TimelineKey
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

    @abstractmethod
    async def page_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        after: TimelineKey | None,
        limit: int,
    ) -> list[ProjectEvent]:
        """Return at most ``limit + 1`` events in canonical database order."""
        ...

    @abstractmethod
    async def get_change_for_revision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
    ) -> ProjectEvent | None:
        """Fail-closed relational lookup for one revision change projection."""
        ...


__all__ = ["IProjectEventRepository"]
