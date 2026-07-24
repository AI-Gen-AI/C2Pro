"""
TS-UC-WBS-ITEM-UPDATE-001 — UpdateWBSItemUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.wbs.application.dtos import UpdateWBSItemRequest, WBSItemDTO
from src.wbs.application.use_cases.update_wbs_item import UpdateWBSItemUseCase
from src.wbs.domain.entities.wbs_item import WBSItem


def _make_item(**overrides) -> WBSItem:
    defaults = {
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "name": "Original",
        "code": "1",
    }
    defaults.update(overrides)
    return WBSItem.create(**defaults)


class TestUpdateWBSItemUseCase:
    @pytest.mark.asyncio
    async def test_update_name_only(self):
        original = _make_item(name="Original", description="keep me")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=original)
        repo.update = AsyncMock()
        repo.update.return_value = original.with_updated_fields(name="New Name")

        uc = UpdateWBSItemUseCase(repository=repo)
        request = UpdateWBSItemRequest(name="New Name")

        result = await uc.execute(
            item_id=original.id,
            tenant_id=original.tenant_id,
            request=request,
        )

        assert isinstance(result, WBSItemDTO)
        assert result.name == "New Name"
        assert result.description == "keep me"
        assert result.code == original.code
        repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_all_fields(self):
        original = _make_item(name="Original")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=original)
        repo.update = AsyncMock()
        updated = original.with_updated_fields(
            name="Updated",
            description="new desc",
            budget_amount=500.0,
            budget_currency="USD",
            completion=75,
        )
        repo.update.return_value = updated

        uc = UpdateWBSItemUseCase(repository=repo)
        request = UpdateWBSItemRequest(
            name="Updated",
            description="new desc",
            budget_amount=500.0,
            budget_currency="USD",
            completion=75,
        )

        result = await uc.execute(
            item_id=original.id,
            tenant_id=original.tenant_id,
            request=request,
        )

        assert result.name == "Updated"
        assert result.description == "new desc"
        assert result.completion == 75

    @pytest.mark.asyncio
    async def test_item_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)

        uc = UpdateWBSItemUseCase(repository=repo)
        request = UpdateWBSItemRequest(name="Wont Work")
        item_id = uuid4()

        with pytest.raises(ValueError, match=str(item_id)):
            await uc.execute(
                item_id=item_id,
                tenant_id=str(uuid4()),
                request=request,
            )
