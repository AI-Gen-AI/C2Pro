"""
TS-UC-WBS-ITEM-CREATE-001 — CreateWBSItemUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.wbs.application.dtos import CreateWBSItemRequest, WBSItemDTO
from src.wbs.application.use_cases.create_wbs_item import CreateWBSItemUseCase
from src.wbs.domain.entities.wbs_item import WBSItem


def _make_item(**overrides) -> WBSItem:
    defaults = {
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "name": "Test Item",
        "code": "1",
    }
    defaults.update(overrides)
    return WBSItem.create(**defaults)


class TestCreateWBSItemUseCase:
    @pytest.mark.asyncio
    async def test_create_root_item_with_explicit_code(self):
        repo = MagicMock()
        repo.create = AsyncMock()
        repo.create.return_value = _make_item(name="Root", code="2")

        uc = CreateWBSItemUseCase(repository=repo)
        request = CreateWBSItemRequest(
            name="Root",
            code="2",
            parent_id=None,
            description="desc",
            start_date=None,
            end_date=None,
            budget_amount=100.0,
            budget_currency="EUR",
            completion=0,
        )

        result = await uc.execute(
            project_id=str(uuid4()),
            tenant_id=str(uuid4()),
            request=request,
        )

        assert isinstance(result, WBSItemDTO)
        assert result.name == "Root"
        assert result.code == "2"
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_child_item_with_auto_code_parent_not_found(self):
        repo = MagicMock()
        repo.get_by_project = AsyncMock(return_value=[])
        repo.get_by_id = AsyncMock(return_value=None)

        uc = CreateWBSItemUseCase(repository=repo)
        request = CreateWBSItemRequest(
            name="Child",
            code=None,
            parent_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Parent not found"):
            await uc.execute(
                project_id=str(uuid4()),
                tenant_id=str(uuid4()),
                request=request,
            )

    @pytest.mark.asyncio
    async def test_create_item_empty_name_raises(self):
        repo = MagicMock()

        uc = CreateWBSItemUseCase(repository=repo)
        request = CreateWBSItemRequest(
            name="",
            code="1",
            parent_id=None,
        )

        with pytest.raises(ValueError, match="name is required"):
            await uc.execute(
                project_id=str(uuid4()),
                tenant_id=str(uuid4()),
                request=request,
            )
