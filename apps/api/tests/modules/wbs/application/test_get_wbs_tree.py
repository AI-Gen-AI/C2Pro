"""
TS-UC-WBS-TREE-GET-001 — GetWBSTreeUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.application.use_cases.get_wbs_tree import (
    GetWBSTreeRequest,
    GetWBSTreeUseCase,
)
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode


def _make_node(**overrides) -> WBSNode:
    defaults = {
        "id": uuid4(),
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "code": "1.0",
        "name": "Root",
        "description": None,
        "lft": 1,
        "rgt": 2,
        "depth": 0,
        "parent_id": None,
        "node_type": WBSNodeType.DELIVERABLE,
        "status": WBSNodeStatus.NOT_STARTED,
        "planned_start": None,
        "planned_end": None,
        "actual_start": None,
        "actual_end": None,
        "budget_allocated": None,
        "budget_spent": 0.0,
        "metadata": {},
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return WBSNode(**defaults)


class TestGetWBSTreeUseCase:
    @pytest.mark.asyncio
    async def test_get_full_tree(self):
        repo = AsyncMock(spec=WBSNodeRepository)
        nodes = [_make_node(code="1.0"), _make_node(code="1.1", lft=2, rgt=3, depth=1)]
        repo.get_tree.return_value = nodes

        uc = GetWBSTreeUseCase(repository=repo)
        request = GetWBSTreeRequest(
            project_id=nodes[0].project_id,
            tenant_id=nodes[0].tenant_id,
            node_id=None,
        )

        result = await uc.execute(request)

        assert result is nodes
        assert len(result) == 2
        repo.get_tree.assert_awaited_once_with(request.project_id, request.tenant_id)

    @pytest.mark.asyncio
    async def test_get_subtree(self):
        repo = AsyncMock(spec=WBSNodeRepository)
        subtree = [_make_node(code="1.1", lft=2, rgt=3, depth=1)]
        repo.get_descendants.return_value = subtree

        uc = GetWBSTreeUseCase(repository=repo)
        node_id = uuid4()
        request = GetWBSTreeRequest(
            project_id=uuid4(),
            tenant_id=uuid4(),
            node_id=node_id,
        )

        result = await uc.execute(request)

        assert result is subtree
        repo.get_descendants.assert_awaited_once_with(
            node_id, request.tenant_id, include_self=True
        )
