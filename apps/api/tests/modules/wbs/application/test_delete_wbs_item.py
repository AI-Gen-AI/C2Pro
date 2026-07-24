"""
TS-UC-WBS-ITEM-DELETE-001 — DeleteWBSItemUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.wbs.application.use_cases.delete_wbs_item import DeleteWBSItemUseCase
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


class TestDeleteWBSItemUseCase:
    @pytest.mark.asyncio
    async def test_delete_leaf_succeeds(self):
        parent = _make_item(name="Parent", code="1")
        child = _make_item(name="Leaf", code="1.1", parent_id=parent.id)
        parent_with_child = parent.add_child(child.id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock()
        repo.get_by_id.side_effect = lambda item_id, tenant_id: {
            child.id: child,
            parent.id: parent_with_child,
        }.get(item_id)
        repo.get_children = AsyncMock(return_value=[])
        repo.update = AsyncMock()
        repo.delete = AsyncMock()

        uc = DeleteWBSItemUseCase(repository=repo)

        result = await uc.execute(
            item_id=child.id,
            tenant_id=child.tenant_id,
            cascade=False,
        )

        assert result is True
        repo.delete.assert_awaited_once_with(child.id, child.tenant_id)

    @pytest.mark.asyncio
    async def test_delete_item_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)

        uc = DeleteWBSItemUseCase(repository=repo)
        item_id = uuid4()

        with pytest.raises(ValueError, match=str(item_id)):
            await uc.execute(
                item_id=item_id,
                tenant_id=str(uuid4()),
            )

    @pytest.mark.asyncio
    async def test_delete_with_children_without_cascade_raises(self):
        item = _make_item(name="Parent", code="1")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=item)
        repo.get_children = AsyncMock(return_value=[MagicMock()])

        uc = DeleteWBSItemUseCase(repository=repo)

        with pytest.raises(ValueError, match="cascade"):
            await uc.execute(
                item_id=item.id,
                tenant_id=item.tenant_id,
                cascade=False,
            )

    @pytest.mark.asyncio
    async def test_delete_with_children_cascade_succeeds(self):
        item = _make_item(name="Parent", code="1")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=item)
        repo.get_children = AsyncMock(return_value=[MagicMock()])
        repo.delete_cascade = AsyncMock()

        uc = DeleteWBSItemUseCase(repository=repo)

        result = await uc.execute(
            item_id=item.id,
            tenant_id=item.tenant_id,
            cascade=True,
        )

        assert result is True
        repo.delete_cascade.assert_awaited_once_with(item.id, item.tenant_id)
