"""
WBS command port abstraction.

Refers to Suite ID: TS-UA-PRJ-UC-002.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.projects.domain.wbs_item_dto import WBSItemDTO


class IWBSCommandPort(Protocol):
    async def create_wbs_item(self, item: WBSItemDTO) -> WBSItemDTO:
        ...

    async def update_wbs_item(self, item: WBSItemDTO) -> WBSItemDTO | None:
        ...

    async def delete_wbs_item(self, item_id: UUID) -> bool:
        ...
