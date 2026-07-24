"""
TS-UC-WBS-NODE-DELETE-001 — DeleteWBSNodeUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.application.use_cases.delete_wbs_node import (
    DeleteWBSNodeRequest,
    DeleteWBSNodeUseCase,
)


class TestDeleteWBSNodeUseCase:
    @pytest.mark.asyncio
    async def test_delete_delegates_to_repo(self):
        repo = AsyncMock(spec=WBSNodeRepository)
        repo.delete.return_value = True

        uc = DeleteWBSNodeUseCase(repository=repo)
        request = DeleteWBSNodeRequest(
            node_id=uuid4(),
            tenant_id=uuid4(),
        )

        result = await uc.execute(request)

        assert result is True
        repo.delete.assert_awaited_once_with(request.node_id, request.tenant_id)

    @pytest.mark.asyncio
    async def test_node_not_found(self):
        repo = AsyncMock(spec=WBSNodeRepository)
        repo.delete.return_value = False

        uc = DeleteWBSNodeUseCase(repository=repo)
        request = DeleteWBSNodeRequest(
            node_id=uuid4(),
            tenant_id=uuid4(),
        )

        result = await uc.execute(request)

        assert result is False
