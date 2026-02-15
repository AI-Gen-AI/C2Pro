"""
WBS Use Cases - Get WBS.

Refers to Suite ID: TS-CT-WBS-API-001
"""

from src.wbs.application.dtos import WBSItemDTO, WBSResponse
from src.wbs.ports import IWBSRepository


class GetWBSUseCase:
    """Use case for getting WBS items for a project."""

    def __init__(self, repository: IWBSRepository):
        self._repository = repository

    async def execute(self, project_id: str, tenant_id: str) -> WBSResponse:
        """Get all WBS items for a project."""
        items = await self._repository.get_by_project(project_id, tenant_id)

        # Build item DTOs with children
        item_dtos = []
        item_map = {item.id: item for item in items}

        for item in items:
            # Get children for this item
            child_items = [item_map[child_id] for child_id in item.children if child_id in item_map]

            children_dtos = [
                {
                    "id": str(child.id),
                    "code": child.code,
                    "name": child.name,
                    "level": child.level,
                }
                for child in child_items
            ]

            dto = WBSItemDTO(
                id=item.id,
                code=item.code,
                name=item.name,
                level=item.level,
                description=item.description,
                parent_id=item.parent_id,
                start_date=item.start_date,
                end_date=item.end_date,
                budget={
                    "amount": item.budget.amount,
                    "currency": item.budget.currency,
                } if item.budget else None,
                completion=item.completion,
                children=children_dtos,
            )
            item_dtos.append(dto)

        # Calculate coverage
        total_items = len(items)
        items_with_budget = sum(1 for item in items if item.budget is not None)
        items_with_dates = sum(1 for item in items if item.start_date is not None and item.end_date is not None)
        items_with_alerts = 0
        completion_average = sum(item.completion for item in items) / total_items if total_items > 0 else 0

        return WBSResponse(
            items=item_dtos,
            coverage={
                "total_items": total_items,
                "items_with_budget": items_with_budget,
                "items_with_dates": items_with_dates,
                "items_with_alerts": items_with_alerts,
                "completion_average": completion_average,
            },
            alerts=[],
        )
