"""
Stakeholders → RACI Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-MOD-STK-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import pytest

from src.stakeholders.application.dtos import RaciGenerationResult, RaciStakeholderInput, RaciWBSItemInput
from src.stakeholders.application.handover_stakeholders_to_raci_use_case import (
    HandoverStakeholdersToRaciUseCase,
)
from src.stakeholders.domain.models import InterestLevel, PowerLevel, Stakeholder
from src.stakeholders.ports.raci_generator import RaciGeneratorPort


@dataclass
class _CapturingRaciGenerator(RaciGeneratorPort):
    stakeholders: list[RaciStakeholderInput] | None = None
    wbs_items: list[RaciWBSItemInput] | None = None

    async def generate_assignments(
        self,
        *,
        wbs_items: list[RaciWBSItemInput],
        stakeholders: list[RaciStakeholderInput],
    ) -> RaciGenerationResult:
        self.wbs_items = wbs_items
        self.stakeholders = stakeholders
        return RaciGenerationResult(assignments=[], warnings=[])


@pytest.mark.asyncio
class TestStakeholdersRaciIntegration:
    """Refers to Suite ID: TS-INT-MOD-STK-001."""

    async def test_handover_maps_stakeholders_for_raci(self) -> None:
        project_id = uuid4()
        stakeholders = [
            Stakeholder(
                id=uuid4(),
                project_id=project_id,
                power_level=PowerLevel.HIGH,
                interest_level=InterestLevel.MEDIUM,
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                name="Alice",
                role="Owner",
                organization="Acme",
                stakeholder_metadata={"type": "internal"},
            ),
            Stakeholder(
                id=uuid4(),
                project_id=project_id,
                power_level=PowerLevel.LOW,
                interest_level=InterestLevel.HIGH,
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                name="Bob",
                role="PM",
                organization="BuilderCo",
                stakeholder_metadata={},
            ),
        ]
        wbs_items = [
            RaciWBSItemInput(
                id=uuid4(),
                name="Foundation",
                description="Base works",
                clause_text="Clause 1.1",
            )
        ]

        generator = _CapturingRaciGenerator()
        use_case = HandoverStakeholdersToRaciUseCase(raci_generator=generator)

        result = await use_case.execute(
            project_id=project_id,
            wbs_items=wbs_items,
            stakeholders=stakeholders,
        )

        assert result.assignments == []
        assert generator.wbs_items == wbs_items
        assert generator.stakeholders == [
            RaciStakeholderInput(
                id=stakeholders[0].id,
                name="Alice",
                role="Owner",
                company="Acme",
                stakeholder_type="internal",
            ),
            RaciStakeholderInput(
                id=stakeholders[1].id,
                name="Bob",
                role="PM",
                company="BuilderCo",
                stakeholder_type=None,
            ),
        ]

    async def test_handover_requires_stakeholders(self) -> None:
        use_case = HandoverStakeholdersToRaciUseCase(raci_generator=_CapturingRaciGenerator())

        with pytest.raises(ValueError):
            await use_case.execute(
                project_id=uuid4(),
                wbs_items=[],
                stakeholders=[],
            )
