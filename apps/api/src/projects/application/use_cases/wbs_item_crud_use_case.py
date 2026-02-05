"""
WBS Item CRUD Use Case.

Refers to Suite ID: TS-UA-PRJ-UC-002.
"""

from __future__ import annotations

from uuid import UUID

from src.projects.domain.wbs_item_dto import WBSItemDTO
from src.projects.ports.wbs_command_port import IWBSCommandPort


class WBSItemCrudUseCase:
    """Orchestrates CRUD operations for WBS items."""

    def __init__(self, wbs_command_port: IWBSCommandPort) -> None:
        self._wbs_command_port = wbs_command_port

    async def create(self, item: WBSItemDTO) -> WBSItemDTO:
        return await self._wbs_command_port.create_wbs_item(item)

    async def update(self, item: WBSItemDTO) -> WBSItemDTO | None:
        return await self._wbs_command_port.update_wbs_item(item)

    async def delete(self, item_id: UUID) -> bool:
        return await self._wbs_command_port.delete_wbs_item(item_id)
