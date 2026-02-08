"""
WBS → Procurement Integration Use Case.

Refers to Suite ID: TS-INT-MOD-WBS-001.
"""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

from src.procurement.domain.models import WBSItem
from src.procurement.ports.wbs_repository import IWBSRepository
from src.projects.domain.wbs_item_dto import WBSItemDTO


class ImportWBSFromProjectsUseCase:
    """Maps Project WBS DTOs into Procurement WBS items."""

    def __init__(self, wbs_repository: IWBSRepository) -> None:
        self._wbs_repository = wbs_repository

    async def execute(
        self,
        project_id: UUID,
        tenant_id: UUID,
        items: list[WBSItemDTO],
    ) -> list[WBSItem]:
        mapped_items: list[WBSItem] = []

        for item in items:
            if item.project_id != project_id:
                raise ValueError("project_id mismatch")

            metadata: dict = {}
            if item.specifications:
                metadata.update(item.specifications)
            if item.parent_id:
                metadata["parent_id"] = str(item.parent_id)

            mapped_items.append(
                WBSItem(
                    project_id=project_id,
                    code=item.code,
                    name=item.name,
                    level=item.level,
                    planned_start=datetime.combine(item.start_date, time.min),
                    planned_end=datetime.combine(item.end_date, time.min),
                    wbs_metadata=metadata,
                )
            )

        return await self._wbs_repository.bulk_create(mapped_items)
