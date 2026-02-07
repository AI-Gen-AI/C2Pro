"""
Stakeholders → RACI handover use case.

Refers to Suite ID: TS-INT-MOD-STK-001.
"""

from __future__ import annotations

from uuid import UUID

from src.stakeholders.application.dtos import RaciStakeholderInput, RaciWBSItemInput, RaciGenerationResult
from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.raci_generator import RaciGeneratorPort


class HandoverStakeholdersToRaciUseCase:
    """Maps stakeholders to RACI generator inputs."""

    def __init__(self, *, raci_generator: RaciGeneratorPort) -> None:
        self._raci_generator = raci_generator

    async def execute(
        self,
        *,
        project_id: UUID,
        wbs_items: list[RaciWBSItemInput],
        stakeholders: list[Stakeholder],
    ) -> RaciGenerationResult:
        if not stakeholders:
            raise ValueError("stakeholders are required")

        mapped = [
            RaciStakeholderInput(
                id=stakeholder.id,
                name=stakeholder.name,
                role=stakeholder.role,
                company=stakeholder.organization,
                stakeholder_type=(
                    stakeholder.stakeholder_metadata.get("type")
                    if isinstance(stakeholder.stakeholder_metadata, dict)
                    else None
                ),
            )
            for stakeholder in stakeholders
        ]

        return await self._raci_generator.generate_assignments(
            wbs_items=wbs_items,
            stakeholders=mapped,
        )
