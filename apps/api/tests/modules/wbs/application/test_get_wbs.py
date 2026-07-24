"""
TS-UC-WBS-GET-001 — GetWBSUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.wbs.application.dtos import WBSResponse
from src.wbs.application.use_cases.get_wbs import GetWBSUseCase
from src.wbs.domain.entities.wbs_item import WBSItem


def _make_item(**overrides) -> WBSItem:
    defaults: dict = {
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "name": "Item",
        "code": "1",
    }
    defaults.update(overrides)
    return WBSItem.create(**defaults)


class TestGetWBSUseCase:
    @pytest.mark.asyncio
    async def test_returns_coverage_for_populated_project(self):
        item1 = _make_item(
            name="Task A",
            code="1",
            budget_amount=1000.0,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 1),
            completion=50,
        )
        item2 = _make_item(
            name="Task B",
            code="2",
            budget_amount=2000.0,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 7, 1),
            completion=100,
        )

        repo = MagicMock()
        repo.get_by_project = AsyncMock(return_value=[item1, item2])

        uc = GetWBSUseCase(repository=repo)
        result = await uc.execute(
            project_id=item1.project_id,
            tenant_id=item1.tenant_id,
        )

        assert isinstance(result, WBSResponse)
        assert result.coverage["total_items"] == 2
        assert result.coverage["items_with_budget"] == 2
        assert result.coverage["items_with_dates"] == 2
        assert result.coverage["items_with_alerts"] == 0
        assert result.coverage["completion_average"] == 75.0
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_empty_project_returns_zero_coverage(self):
        repo = MagicMock()
        repo.get_by_project = AsyncMock(return_value=[])

        uc = GetWBSUseCase(repository=repo)
        result = await uc.execute(
            project_id=str(uuid4()),
            tenant_id=str(uuid4()),
        )

        assert isinstance(result, WBSResponse)
        assert result.coverage["total_items"] == 0
        assert result.coverage["items_with_budget"] == 0
        assert result.coverage["items_with_dates"] == 0
        assert result.coverage["items_with_alerts"] == 0
        assert result.coverage["completion_average"] == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_completion_average_is_correct(self):
        item1 = _make_item(name="A", code="1", completion=30)
        item2 = _make_item(name="B", code="2", completion=70)
        item3 = _make_item(name="C", code="3", completion=50)

        repo = MagicMock()
        repo.get_by_project = AsyncMock(return_value=[item1, item2, item3])

        uc = GetWBSUseCase(repository=repo)
        result = await uc.execute(
            project_id=item1.project_id,
            tenant_id=item1.tenant_id,
        )

        assert result.coverage["completion_average"] == 50.0
        assert result.coverage["total_items"] == 3
