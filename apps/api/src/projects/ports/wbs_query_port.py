"""
WBS query port abstraction.

Refers to Suite ID: TS-UD-PRJ-DTO-001.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.projects.domain.wbs_item_dto import WBSItemDTO


class IWBSQueryPort(Protocol):
    def get_wbs_items_for_project(self, project_id: UUID, level: int | None = None) -> list[WBSItemDTO]: ...

    def get_wbs_item_by_id(self, item_id: UUID) -> WBSItemDTO | None: ...

    def wbs_item_exists(self, item_id: UUID) -> bool: ...
