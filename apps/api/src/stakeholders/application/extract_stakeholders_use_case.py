"""
Extract Stakeholders Use Case.

Refers to Suite ID: TS-UA-STK-UC-001.
"""

from __future__ import annotations

from uuid import UUID

from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.stakeholder_extraction_service import (
    IStakeholderExtractionService,
)
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class ExtractStakeholdersUseCase:
    """Refers to Suite ID: TS-UA-STK-UC-001."""

    def __init__(
        self,
        *,
        stakeholder_repository: IStakeholderRepository,
        extraction_service: IStakeholderExtractionService,
    ) -> None:
        self.stakeholder_repository = stakeholder_repository
        self.extraction_service = extraction_service

    async def execute(
        self,
        *,
        contract_text: str,
        project_id: UUID,
        tenant_id: UUID,
    ) -> list[Stakeholder]:
        """Extract and persist stakeholders from contract text."""
        stakeholders = await self.extraction_service.extract_from_text(
            text=contract_text,
            project_id=project_id,
            tenant_id=tenant_id,
        )
        if not stakeholders:
            return []

        for stakeholder in stakeholders:
            await self.stakeholder_repository.add(stakeholder)
        await self.stakeholder_repository.commit()
        return stakeholders
