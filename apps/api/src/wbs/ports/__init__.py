"""WBS ports (interfaces)."""

from typing import Any, Protocol
from uuid import UUID

from src.wbs.domain.entities.wbs_item import WBSItem


class IWBSRepository(Protocol):
    """
    Repository port for WBS items.

    Refers to Suite ID: TS-CT-WBS-API-001
    """

    async def get_by_id(self, item_id: UUID, tenant_id: str) -> WBSItem | None:
        """Get a WBS item by ID."""
        ...

    async def get_by_project(self, project_id: str, tenant_id: str) -> list[WBSItem]:
        """Get all WBS items for a project."""
        ...

    async def get_by_code(self, project_id: str, code: str, tenant_id: str) -> WBSItem | None:
        """Get a WBS item by code."""
        ...

    async def create(self, item: WBSItem) -> WBSItem:
        """Create a new WBS item."""
        ...

    async def update(self, item: WBSItem) -> WBSItem:
        """Update an existing WBS item."""
        ...

    async def delete(self, item_id: UUID, tenant_id: str) -> bool:
        """Delete a WBS item."""
        ...

    async def get_children(self, parent_id: UUID, tenant_id: str) -> list[WBSItem]:
        """Get all children of a WBS item."""
        ...

    async def delete_cascade(self, item_id: UUID, tenant_id: str) -> int:
        """Delete a WBS item and all its descendants. Returns count deleted."""
        ...


class IWBSQueryPort(Protocol):
    """
    Query port for cross-module WBS access.

    Refers to Suite ID: TS-UD-PRJ-DTO-001
    """

    async def get_wbs_items_for_project(
        self, project_id: str, tenant_id: str, level: int | None = None
    ) -> list[dict[str, Any]]:
        """Get WBS items for a project (as dicts for DTO serialization)."""
        ...

    async def get_wbs_item_by_id(self, item_id: UUID, tenant_id: str) -> dict[str, Any] | None:
        """Get a WBS item by ID."""
        ...

    async def wbs_item_exists(self, item_id: UUID, tenant_id: str) -> bool:
        """Check if a WBS item exists."""
        ...
