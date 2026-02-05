"""
Generate WBS Use Case Tests (TDD - RED Phase)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.projects.application.use_cases.generate_wbs_use_case import GenerateWBSUseCase
from src.projects.domain.wbs_item_dto import WBSItemDTO


class TestGenerateWBSUseCase:
    """Refers to Suite ID: TS-UA-PRJ-UC-001."""

    @pytest.mark.asyncio
    async def test_generate_wbs_use_case_returns_items(self) -> None:
        project_id = uuid4()
        contract_text = "Contract scope for civil works and procurement."
        expected = [
            WBSItemDTO(
                id=uuid4(),
                project_id=project_id,
                code="1",
                name="Civil Works",
                level=1,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 1),
            )
        ]

        port = AsyncMock()
        port.generate_wbs.return_value = expected

        use_case = GenerateWBSUseCase(port)

        result = await use_case.execute(project_id=project_id, contract_text=contract_text)

        assert result == expected
        port.generate_wbs.assert_awaited_once_with(project_id, contract_text)
