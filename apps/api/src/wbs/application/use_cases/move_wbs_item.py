"""
WBS Use Cases - Move WBS Item.

Refers to Suite ID: TS-CT-WBS-API-001
"""

from typing import Any
from uuid import UUID

from src.wbs.application.dtos import MoveWBSItemRequest, WBSItemDTO
from src.wbs.application.mappers import map_wbs_item_to_dto
from src.wbs.domain.entities.wbs_item import WBSItem
from src.wbs.ports import IWBSRepository


class MoveWBSItemUseCase:
    """Use case for moving a WBS item."""

    def __init__(self, repository: IWBSRepository):
        self._repository = repository

    async def execute(
        self,
        item_id: UUID,
        project_id: str,
        tenant_id: str,
        request: MoveWBSItemRequest,
    ) -> WBSItemDTO:
        """Move a WBS item to a new parent."""
        item = await self._repository.get_by_id(item_id, tenant_id)
        if item is None:
            raise ValueError(f"WBS item with ID {item_id} not found")

        # Get all items for validation
        all_items = await self._repository.get_by_project(project_id, tenant_id)
        all_items_map = {item.id: item for item in all_items}

        # Validate move
        if not item.can_be_moved_to(request.new_parent_id, all_items_map):
            if request.new_parent_id == item_id:
                raise ValueError("Cannot move item to itself (circular reference)")
            raise ValueError(
                "Cannot move item: would exceed maximum depth or create circular reference"
            )

        # Remove from old parent
        if item.parent_id is not None:
            old_parent = await self._repository.get_by_id(item.parent_id, tenant_id)
            if old_parent:
                updated_old_parent = old_parent.remove_child(item_id)
                await self._repository.update(updated_old_parent)

        # Generate new code based on new parent
        new_parent_id = request.new_parent_id
        new_code = await self._generate_new_code(item, new_parent_id, all_items)

        # Update item
        updated_item = item.with_updated_fields(
            parent_id=new_parent_id,
            code=new_code,
        )

        saved = await self._repository.update(updated_item)

        # Add to new parent
        if new_parent_id is not None:
            new_parent = await self._repository.get_by_id(new_parent_id, tenant_id)
            if new_parent:
                updated_new_parent = new_parent.add_child(saved.id)
                await self._repository.update(updated_new_parent)

        return map_wbs_item_to_dto(saved, children=[])

    async def _generate_new_code(
        self, item: WBSItem, new_parent_id: UUID | None, all_items: list[WBSItem]
    ) -> str:
        """Generate new code when moving item to new parent."""
        if new_parent_id is not None:
            # Find new parent and generate sibling code
            all_items_map = {i.id: i for i in all_items}
            new_parent = all_items_map.get(new_parent_id)
            if new_parent:
                siblings = [i for i in all_items if i.parent_id == new_parent_id]
                if siblings:
                    max_num = max(int(i.code.split(".")[-1]) for i in siblings)
                    return f"{new_parent.code}.{max_num + 1}"
                else:
                    return f"{new_parent.code}.1"
            return item.code
        else:
            # Moving to root
            root_items = [i for i in all_items if i.parent_id is None]
            if root_items:
                max_num = max(int(i.code) for i in root_items)
                return str(max_num + 1)
            return "1"
