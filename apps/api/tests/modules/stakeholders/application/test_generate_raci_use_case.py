"""
Generate RACI Use Case tests.

Refers to Suite ID: TS-UA-STK-UC-002.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.stakeholders.application.generate_raci_use_case import GenerateRaciUseCase
from src.stakeholders.application.dtos import RaciGenerationAssignment, RaciGenerationResult
from src.stakeholders.domain.models import RACIRole


class TestGenerateRaciUseCase:
    """Refers to Suite ID: TS-UA-STK-UC-002."""

    @pytest.mark.asyncio
    async def test_001_generates_raci_assignments(self) -> None:
        project_id = uuid4()
        result = RaciGenerationResult(
            assignments=[
                RaciGenerationAssignment(
                    wbs_item_id=uuid4(),
                    stakeholder_id=uuid4(),
                    role=RACIRole.ACCOUNTABLE,
                    evidence_text="Clause",
                )
            ],
            warnings=[],
        )

        service = AsyncMock()
        service.generate_and_persist.return_value = result

        use_case = GenerateRaciUseCase(raci_generation_service=service)

        response = await use_case.execute(project_id=project_id)

        service.generate_and_persist.assert_awaited_once_with(project_id)
        assert response == result

    @pytest.mark.asyncio
    async def test_002_returns_empty_result(self) -> None:
        project_id = uuid4()
        result = RaciGenerationResult(assignments=[], warnings=["no data"])

        service = AsyncMock()
        service.generate_and_persist.return_value = result

        use_case = GenerateRaciUseCase(raci_generation_service=service)

        response = await use_case.execute(project_id=project_id)

        assert response.assignments == []
        assert response.warnings == ["no data"]
