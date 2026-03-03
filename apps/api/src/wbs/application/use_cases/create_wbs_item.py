"""
WBS Use Cases - Create WBS Item.

Refers to Suite ID: TS-CT-WBS-API-001
"""

from uuid import UUID

from src.wbs.application.dtos import CreateWBSItemRequest, WBSItemDTO
from src.wbs.application.mappers import map_wbs_item_to_dto
from src.wbs.domain.entities.wbs_item import WBSItem
from src.wbs.ports import IWBSRepository


class CreateWBSItemUseCase:
    """Use case for creating a WBS item."""

    def __init__(self, repository: IWBSRepository):
        self._repository = repository

    async def execute(
        self,
        project_id: str,
        tenant_id: str,
        request: CreateWBSItemRequest,
    ) -> WBSItemDTO:
        """Create a new WBS item."""
        # Auto-generate code if not provided
        code = request.code
        if code is None:
            code = await self._generate_code(project_id, tenant_id, request.parent_id)

        item = WBSItem.create(
            project_id=project_id,
            tenant_id=tenant_id,
            name=request.name,
            code=code,
            parent_id=request.parent_id,
            description=request.description,
            start_date=request.start_date,
            end_date=request.end_date,
            budget_amount=request.budget_amount,
            budget_currency=request.budget_currency,
            completion=request.completion,
        )

        created = await self._repository.create(item)

        # Update parent with new child
        if request.parent_id is not None:
            parent = await self._repository.get_by_id(request.parent_id, tenant_id)
            if parent:
                updated_parent = parent.add_child(created.id)
                await self._repository.update(updated_parent)

        return map_wbs_item_to_dto(created, children=[])

    async def _generate_code(
        self,
        project_id: str,
        tenant_id: str,
        parent_id: UUID | None,
    ) -> str:
        """Generate the next available code."""
        items = await self._repository.get_by_project(project_id, tenant_id)

        if parent_id is None:
            # Root level - find highest number
            root_items = [item for item in items if item.parent_id is None]
            if not root_items:
                return "1"
            max_num = max(int(item.code) for item in root_items)
            return str(max_num + 1)
        else:
            # Child level - find siblings
            parent = await self._repository.get_by_id(parent_id, tenant_id)
            if not parent:
                raise ValueError("Parent not found")

            sibling_items = [item for item in items if item.parent_id == parent_id]
            if not sibling_items:
                return f"{parent.code}.1"

            # Extract last number from codes
            max_num = 0
            for item in sibling_items:
                last_part = item.code.split(".")[-1]
                max_num = max(max_num, int(last_part))

            return f"{parent.code}.{max_num + 1}"
