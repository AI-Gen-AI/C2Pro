"""Port for the ProjectState aggregate repository (ADR-014 / TASK-V3-014-02).

Hexagonal port — application/domain depend on this ABC, not on SQLAlchemy.

LOCKED INVARIANT: implementations MUST NOT call ``session.commit()``. The unit of
work is owned by the application use case (one transaction per request). Enforced
by ``tests/unit/project_state/test_no_commit_in_repository.py``.

Tenant isolation is mandatory on every read/write (RLS at the DB layer +
``tenant_id`` on the aggregate).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.project_state.domain.aggregate import ProjectState


class ProjectStateRepository(ABC):
    """Repository interface for the ProjectState aggregate."""

    @abstractmethod
    async def get(self, project_id: UUID, tenant_id: UUID) -> ProjectState | None:
        """Load the canonical ProjectState for a project (tenant-isolated)."""
        ...

    @abstractmethod
    async def save(self, state: ProjectState) -> ProjectState:
        """Persist the aggregate (upsert). MUST NOT ``commit()`` — the use case owns the transaction."""
        ...


__all__ = ["ProjectStateRepository"]
