"""
TS-UC-WBS-UPDATE-001 — UpdateWBSNodeUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.wbs.application.use_cases.update_wbs_node import (
    UpdateWBSNodeRequest,
    UpdateWBSNodeUseCase,
)
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode


def _make_node(**overrides) -> WBSNode:
    defaults = {
        "id": uuid4(),
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "code": "1.0",
        "name": "Old Name",
        "description": "old",
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


class TestUpdateWBSNodeUseCase:
    @pytest.mark.asyncio
    async def test_001_update_all_fields_delegates_to_repo(self):
        repo = AsyncMock()
        expected_node = _make_node(name="Updated")
        repo.update.return_value = expected_node

        uc = UpdateWBSNodeUseCase(repository=repo)
        request = UpdateWBSNodeRequest(
            node_id=expected_node.id,
            tenant_id=expected_node.tenant_id,
            name="Updated",
            description="new desc",
            status=WBSNodeStatus.IN_PROGRESS,
            node_type=WBSNodeType.WORK_PACKAGE,
            planned_start=datetime(2026, 2, 1),
            planned_end=datetime(2026, 3, 1),
            actual_start=datetime(2026, 2, 5),
            actual_end=datetime(2026, 2, 20),
            budget_allocated=500.0,
            budget_spent=200.0,
            metadata={"k": "v"},
        )

        result = await uc.execute(request)

        assert result is expected_node
        repo.update.assert_awaited_once_with(
            request.node_id,
            request.tenant_id,
            name="Updated",
            description="new desc",
            status=WBSNodeStatus.IN_PROGRESS,
            node_type=WBSNodeType.WORK_PACKAGE,
            planned_start=datetime(2026, 2, 1),
            planned_end=datetime(2026, 3, 1),
            actual_start=datetime(2026, 2, 5),
            actual_end=datetime(2026, 2, 20),
            budget_allocated=500.0,
            budget_spent=200.0,
            metadata={"k": "v"},
        )

    @pytest.mark.asyncio
    async def test_002_update_only_some_fields_filters_none(self):
        repo = AsyncMock()
        expected_node = _make_node(name="Partial")
        repo.update.return_value = expected_node

        uc = UpdateWBSNodeUseCase(repository=repo)
        request = UpdateWBSNodeRequest(
            node_id=expected_node.id,
            tenant_id=expected_node.tenant_id,
            name="Partial",
            budget_allocated=300.0,
        )

        await uc.execute(request)

        repo.update.assert_awaited_once_with(
            request.node_id,
            request.tenant_id,
            name="Partial",
            budget_allocated=300.0,
        )

    @pytest.mark.asyncio
    async def test_003_node_not_found_returns_none(self):
        repo = AsyncMock()
        repo.update.return_value = None

        uc = UpdateWBSNodeUseCase(repository=repo)
        request = UpdateWBSNodeRequest(
            node_id=uuid4(),
            tenant_id=uuid4(),
            name="Unfindable",
        )

        result = await uc.execute(request)

        assert result is None

    @pytest.mark.asyncio
    async def test_004_empty_update_passes_empty_kwargs(self):
        repo = AsyncMock()
        expected_node = _make_node()
        repo.update.return_value = expected_node

        uc = UpdateWBSNodeUseCase(repository=repo)
        request = UpdateWBSNodeRequest(
            node_id=expected_node.id,
            tenant_id=expected_node.tenant_id,
        )

        await uc.execute(request)

        repo.update.assert_awaited_once_with(
            request.node_id,
            request.tenant_id,
        )
