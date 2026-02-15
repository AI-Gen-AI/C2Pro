"""
In-memory WBS repository (fake implementation for GREEN phase).

Refers to Suite ID: TS-CT-WBS-API-001
"""

from uuid import UUID

from src.wbs.domain.entities.wbs_item import WBSItem
from src.wbs.ports import IWBSRepository


class InMemoryWBSRepository(IWBSRepository):
    """
    In-memory repository for WBS items.

    Used for GREEN phase to make tests pass quickly.
    Will be replaced with SQLAlchemy repository.
    """

    def __init__(self):
        self._items: dict[UUID, WBSItem] = {}

    async def get_by_id(self, item_id: UUID, tenant_id: str) -> WBSItem | None:
        """Get a WBS item by ID."""
        item = self._items.get(item_id)
        if item and item.tenant_id == tenant_id:
            return item
        return None

    async def get_by_project(self, project_id: str, tenant_id: str) -> list[WBSItem]:
        """Get all WBS items for a project."""
        return [
            item for item in self._items.values()
            if item.project_id == project_id and item.tenant_id == tenant_id
        ]

    async def get_by_code(self, project_id: str, code: str, tenant_id: str) -> WBSItem | None:
        """Get a WBS item by code."""
        for item in self._items.values():
            if (item.project_id == project_id and
                item.code == code and
                item.tenant_id == tenant_id):
                return item
        return None

    async def create(self, item: WBSItem) -> WBSItem:
        """Create a new WBS item."""
        self._items[item.id] = item
        return item

    async def update(self, item: WBSItem) -> WBSItem:
        """Update an existing WBS item."""
        self._items[item.id] = item
        return item

    async def delete(self, item_id: UUID, tenant_id: str) -> bool:
        """Delete a WBS item."""
        item = self._items.get(item_id)
        if item and item.tenant_id == tenant_id:
            del self._items[item_id]
            return True
        return False

    async def get_children(self, parent_id: UUID, tenant_id: str) -> list[WBSItem]:
        """Get all children of a WBS item."""
        return [
            item for item in self._items.values()
            if item.parent_id == parent_id and item.tenant_id == tenant_id
        ]

    async def delete_cascade(self, item_id: UUID, tenant_id: str) -> int:
        """Delete a WBS item and all its descendants."""
        # Get all descendants
        to_delete = [item_id]
        count = 0

        # Find all items that are descendants
        for item in list(self._items.values()):
            if item.tenant_id == tenant_id:
                # Check if this item is a descendant of item_id
                parent = self._items.get(item.parent_id) if item.parent_id else None
                while parent:
                    if parent.id == item_id:
                        to_delete.append(item.id)
                        break
                    parent = self._items.get(parent.parent_id) if parent.parent_id else None

        # Delete all
        for id_to_delete in to_delete:
            if id_to_delete in self._items:
                item = self._items[id_to_delete]
                if item.tenant_id == tenant_id:
                    del self._items[id_to_delete]
                    count += 1

        return count

    def clear(self) -> None:
        """Clear all items (for testing)."""
        self._items.clear()


# Singleton instance for the application
_wbs_repository = InMemoryWBSRepository()


def get_wbs_repository() -> InMemoryWBSRepository:
    """Get the singleton WBS repository instance."""
    return _wbs_repository
