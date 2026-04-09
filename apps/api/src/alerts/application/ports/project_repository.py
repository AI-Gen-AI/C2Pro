"""
Project Repository Port.

Interface for project operations needed by alerts module.
TASK-IMPL-008: Added missing Project import.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.projects.domain.models import Project


class IProjectRepository(Protocol):
    """Repository interface for Project operations."""

    async def get_by_id(self, project_id, tenant_id) -> "Project | None":
        """Get project by ID with tenant isolation."""
        ...

    async def exists(self, project_id, tenant_id) -> bool:
        """Check if project exists for tenant."""
        ...
