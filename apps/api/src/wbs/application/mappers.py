"""
WBS Application Mappers.

Refers to Suite ID: TS-CT-WBS-API-001 (REFACTOR phase)
"""

from src.wbs.application.dtos import WBSItemDTO
from src.wbs.domain.entities.wbs_item import WBSItem


def map_wbs_item_to_dto(item: WBSItem, children: list[dict] | None = None) -> WBSItemDTO:
    """
    Map a domain WBSItem to a WBSItemDTO.

    Args:
        item: The domain entity to map
        children: Optional list of child item dicts

    Returns:
        WBSItemDTO for API responses
    """
    return WBSItemDTO(
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
        children=children if children is not None else [],
    )
