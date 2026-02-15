"""
WBS Use Cases - Delete WBS Item.

Refers to Suite ID: TS-CT-WBS-API-001
"""

from uuid import UUID

from src.wbs.ports import IWBSRepository


class DeleteWBSItemUseCase:
    """Use case for deleting a WBS item."""

    def __init__(self, repository: IWBSRepository):
        self._repository = repository

    async def execute(
        self,
        item_id: UUID,
        tenant_id: str,
        cascade: bool = False,
    ) -> bool:
        """Delete a WBS item."""
        item = await self._repository.get_by_id(item_id, tenant_id)
        if item is None:
            raise ValueError(f"WBS item with ID {item_id} not found")

        # Check for children
        children = await self._repository.get_children(item_id, tenant_id)
        if children and not cascade:
            raise ValueError("Cannot delete item with children without cascade=True")

        # Remove from parent
        if item.parent_id is not None:
            parent = await self._repository.get_by_id(item.parent_id, tenant_id)
            if parent:
                updated_parent = parent.remove_child(item_id)
                await self._repository.update(updated_parent)

        if cascade:
            # Delete item and all descendants
            await self._repository.delete_cascade(item_id, tenant_id)
        else:
            await self._repository.delete(item_id, tenant_id)

        return True
