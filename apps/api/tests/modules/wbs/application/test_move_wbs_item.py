"""
TS-UC-WBS-ITEM-MOVE-001 — MoveWBSItemUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.wbs.application.dtos import MoveWBSItemRequest
from src.wbs.application.use_cases.move_wbs_item import MoveWBSItemUseCase
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


class TestMoveWBSItemUseCase:
    @pytest.mark.asyncio
    async def test_move_item_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)

        uc = MoveWBSItemUseCase(repository=repo)
        request = MoveWBSItemRequest(new_parent_id=uuid4())
        item_id = uuid4()

        with pytest.raises(ValueError, match=str(item_id)):
            await uc.execute(
                item_id=item_id,
                project_id=str(uuid4()),
                tenant_id=str(uuid4()),
                request=request,
            )

    @pytest.mark.asyncio
    async def test_move_to_same_parent_triggers_validation(self):
        parent = _make_item(name="Parent", code="1")
        child = _make_item(name="Child", code="1.1", parent_id=parent.id)
        parent = parent.add_child(child.id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock()
        repo.get_by_id.side_effect = lambda item_id, tenant_id: {
            child.id: child,
            parent.id: parent,
        }.get(item_id)
        repo.get_by_project = AsyncMock(return_value=[parent, child])
        repo.update = AsyncMock(return_value=child)

        uc = MoveWBSItemUseCase(repository=repo)
        request = MoveWBSItemRequest(new_parent_id=parent.id)

        result = await uc.execute(
            item_id=child.id,
            project_id=child.project_id,
            tenant_id=child.tenant_id,
            request=request,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_move_circular_raises(self):
        item = _make_item(name="Item", code="1")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=item)
        repo.get_by_project = AsyncMock(return_value=[item])

        uc = MoveWBSItemUseCase(repository=repo)
        request = MoveWBSItemRequest(new_parent_id=item.id)

        with pytest.raises(ValueError, match="circular"):
            await uc.execute(
                item_id=item.id,
                project_id=item.project_id,
                tenant_id=item.tenant_id,
                request=request,
            )
