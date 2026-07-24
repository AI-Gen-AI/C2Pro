"""
TS-UC-WBS-CREATE-001 — CreateWBSNodeUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.wbs.application.use_cases.create_wbs_node import (
    CreateWBSNodeRequest,
    CreateWBSNodeUseCase,
)
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode


def _make_node(**overrides) -> WBSNode:
    """Minimal WBSNode factory."""
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


class TestCreateWBSNodeUseCase:
    @pytest.mark.asyncio
    async def test_001_root_node_creation_delegates_to_repo(self):
        repo = AsyncMock()
        expected_node = _make_node()
        repo.create.return_value = expected_node

        uc = CreateWBSNodeUseCase(repository=repo)
        request = CreateWBSNodeRequest(
            project_id=expected_node.project_id,
            tenant_id=expected_node.tenant_id,
            code="1.0",
            name="Root Node",
            node_type=WBSNodeType.DELIVERABLE,
            parent_id=None,
            description="desc",
            status=WBSNodeStatus.NOT_STARTED,
            planned_start=None,
            planned_end=None,
            budget_allocated=100.0,
            metadata={"key": "value"},
        )

        result = await uc.execute(request)

        assert result is expected_node
        repo.create.assert_awaited_once_with(
            project_id=request.project_id,
            tenant_id=request.tenant_id,
            code=request.code,
            name=request.name,
            parent_id=None,
            node_type=request.node_type,
            description=request.description,
            status=request.status,
            planned_start=request.planned_start,
            planned_end=request.planned_end,
            budget_allocated=request.budget_allocated,
            metadata=request.metadata,
        )

    @pytest.mark.asyncio
    async def test_002_child_node_creation_delegates_to_repo(self):
        repo = AsyncMock()
        expected_node = _make_node(parent_id=uuid4(), depth=1)
        repo.create.return_value = expected_node

        uc = CreateWBSNodeUseCase(repository=repo)
        request = CreateWBSNodeRequest(
            project_id=expected_node.project_id,
            tenant_id=expected_node.tenant_id,
            code="1.1",
            name="Child Node",
            node_type=WBSNodeType.WORK_PACKAGE,
            parent_id=expected_node.parent_id,
        )

        result = await uc.execute(request)

        assert result is expected_node
        repo.create.assert_awaited_once_with(
            project_id=request.project_id,
            tenant_id=request.tenant_id,
            code=request.code,
            name=request.name,
            parent_id=request.parent_id,
            node_type=request.node_type,
            description=None,
            status=WBSNodeStatus.NOT_STARTED,
            planned_start=None,
            planned_end=None,
            budget_allocated=None,
            metadata={},
        )

    @pytest.mark.asyncio
    async def test_003_metadata_none_defaults_to_empty_dict(self):
        repo = AsyncMock()
        expected_node = _make_node()
        repo.create.return_value = expected_node

        uc = CreateWBSNodeUseCase(repository=repo)
        request = CreateWBSNodeRequest(
            project_id=expected_node.project_id,
            tenant_id=expected_node.tenant_id,
            code="2.0",
            name="Test",
            node_type=WBSNodeType.MILESTONE,
            metadata=None,
        )

        await uc.execute(request)

        _, kwargs = repo.create.await_args
        assert kwargs["metadata"] == {}
