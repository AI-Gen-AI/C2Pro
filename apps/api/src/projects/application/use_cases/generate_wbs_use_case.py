"""
Generate WBS Use Case.

Refers to Suite ID: TS-UA-PRJ-UC-001.
"""

from __future__ import annotations

from uuid import UUID

from src.projects.domain.wbs_item_dto import WBSItemDTO
from src.projects.ports.wbs_generation_port import IWBSGenerationPort


class GenerateWBSUseCase:
    """Orchestrates WBS generation for a project."""

    def __init__(self, wbs_generation_port: IWBSGenerationPort) -> None:
        self._wbs_generation_port = wbs_generation_port

    async def execute(self, project_id: UUID, contract_text: str) -> list[WBSItemDTO]:
        return await self._wbs_generation_port.generate_wbs(project_id, contract_text)
