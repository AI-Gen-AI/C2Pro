"""
Generate RACI Use Case.

Refers to Suite ID: TS-UA-STK-UC-002.
"""

from __future__ import annotations

from uuid import UUID

from src.stakeholders.application.dtos import RaciGenerationResult
from src.stakeholders.ports.raci_generation_service import IRaciGenerationService


class GenerateRaciUseCase:
    """Refers to Suite ID: TS-UA-STK-UC-002."""

    def __init__(self, *, raci_generation_service: IRaciGenerationService) -> None:
        self.raci_generation_service = raci_generation_service

    async def execute(self, project_id: UUID) -> RaciGenerationResult:
        """Generate RACI assignments for a project."""
        return await self.raci_generation_service.generate_and_persist(project_id)
