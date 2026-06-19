"""Port for ProjectSnapshot append-only repository (ADR-015 / TASK-V3-015-04).

LOCKED INVARIANT: implementations MUST NOT call session commit().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.temporal.domain.project_snapshot import ProjectSnapshot


class IProjectSnapshotRepository(ABC):
    @abstractmethod
    async def append_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        ...

    @abstractmethod
    async def latest(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None:
        ...

    @abstractmethod
    async def list_since(
        self, project_id: UUID, tenant_id: UUID, since: datetime
    ) -> list[ProjectSnapshot]:
        ...


__all__ = ["IProjectSnapshotRepository"]
