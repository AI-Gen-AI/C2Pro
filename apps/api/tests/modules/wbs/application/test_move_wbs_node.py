"""
TS-UC-WBS-NODE-MOVE-001 — MoveWBSNodeUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.application.use_cases.move_wbs_node import (
    MoveWBSNodeRequest,
    MoveWBSNodeUseCase,
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


class TestMoveWBSNodeUseCase:
    @pytest.mark.asyncio
    async def test_move_delegates_to_repo(self):
        repo = AsyncMock(spec=WBSNodeRepository)
        expected_node = _make_node(name="Moved")
        repo.move_node.return_value = expected_node

        uc = MoveWBSNodeUseCase(repository=repo)
        request = MoveWBSNodeRequest(
            node_id=uuid4(),
            tenant_id=uuid4(),
            new_parent_id=uuid4(),
        )

        result = await uc.execute(request)

        assert result is expected_node
        repo.move_node.assert_awaited_once_with(
            node_id=request.node_id,
            tenant_id=request.tenant_id,
            new_parent_id=request.new_parent_id,
        )

    @pytest.mark.asyncio
    async def test_node_not_found_returns_none(self):
        repo = AsyncMock(spec=WBSNodeRepository)
        repo.move_node.return_value = None

        uc = MoveWBSNodeUseCase(repository=repo)
        request = MoveWBSNodeRequest(
            node_id=uuid4(),
            tenant_id=uuid4(),
            new_parent_id=None,
        )

        result = await uc.execute(request)

        assert result is None
