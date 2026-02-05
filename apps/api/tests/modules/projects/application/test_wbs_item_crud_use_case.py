"""
WBS Item CRUD Use Case Tests (TDD - RED Phase)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.projects.application.use_cases.wbs_item_crud_use_case import WBSItemCrudUseCase
from src.projects.domain.wbs_item_dto import WBSItemDTO


class TestWBSItemCrudUseCase:
    """Refers to Suite ID: TS-UA-PRJ-UC-002."""

    @pytest.mark.asyncio
    async def test_create_wbs_item(self) -> None:
        project_id = uuid4()
        dto = WBSItemDTO(
            id=uuid4(),
            project_id=project_id,
            code="1.1",
            name="Excavation",
            level=2,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
        )

        port = AsyncMock()
        port.create_wbs_item.return_value = dto
        use_case = WBSItemCrudUseCase(port)

        result = await use_case.create(dto)

        assert result == dto
        port.create_wbs_item.assert_awaited_once_with(dto)

    @pytest.mark.asyncio
    async def test_delete_wbs_item(self) -> None:
        item_id = uuid4()
        port = AsyncMock()
        port.delete_wbs_item.return_value = True
        use_case = WBSItemCrudUseCase(port)

        result = await use_case.delete(item_id)

        assert result is True
        port.delete_wbs_item.assert_awaited_once_with(item_id)
