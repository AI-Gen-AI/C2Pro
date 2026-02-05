"""
WBS generation port abstraction.

Refers to Suite ID: TS-UA-PRJ-UC-001.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.projects.domain.wbs_item_dto import WBSItemDTO


class IWBSGenerationPort(Protocol):
    async def generate_wbs(self, project_id: UUID, contract_text: str) -> list[WBSItemDTO]:
        ...
