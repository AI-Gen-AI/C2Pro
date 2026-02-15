"""
WBS Use Cases - Update WBS Item.

Refers to Suite ID: TS-CT-WBS-API-001
"""

from uuid import UUID

from src.wbs.application.dtos import UpdateWBSItemRequest, WBSItemDTO
from src.wbs.application.mappers import map_wbs_item_to_dto
from src.wbs.ports import IWBSRepository


class UpdateWBSItemUseCase:
    """Use case for updating a WBS item."""

    def __init__(self, repository: IWBSRepository):
        self._repository = repository

    async def execute(
        self,
        item_id: UUID,
        tenant_id: str,
        request: UpdateWBSItemRequest,
    ) -> WBSItemDTO:
        """Update a WBS item."""
        item = await self._repository.get_by_id(item_id, tenant_id)
        if item is None:
            raise ValueError(f"WBS item with ID {item_id} not found")

        updated = item.with_updated_fields(
            name=request.name,
            description=request.description,
            start_date=request.start_date,
            end_date=request.end_date,
            budget_amount=request.budget_amount,
            budget_currency=request.budget_currency,
            completion=request.completion,
        )

        saved = await self._repository.update(updated)

        return map_wbs_item_to_dto(saved, children=[])
