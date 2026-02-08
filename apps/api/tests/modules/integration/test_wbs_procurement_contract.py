"""
WBS → Procurement Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-MOD-WBS-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

import pytest

from src.procurement.domain.models import WBSItem
from src.procurement.ports.wbs_repository import IWBSRepository
from src.procurement.application.use_cases.import_wbs_from_projects_use_case import (
    ImportWBSFromProjectsUseCase,
)
from src.projects.domain.wbs_item_dto import WBSItemDTO


@dataclass
class _FakeWBSRepository(IWBSRepository):
    created_items: list[WBSItem] = field(default_factory=list)

    async def create(self, wbs_item: WBSItem) -> WBSItem:
        self.created_items.append(wbs_item)
        return wbs_item

    async def bulk_create(self, wbs_items: list[WBSItem]) -> list[WBSItem]:
        self.created_items.extend(wbs_items)
        return wbs_items

    async def get_by_id(self, wbs_id: UUID, tenant_id: UUID) -> WBSItem | None:
        raise NotImplementedError

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        raise NotImplementedError

    async def get_by_code(self, project_id: UUID, wbs_code: str, tenant_id: UUID) -> WBSItem | None:
        raise NotImplementedError

    async def get_children(self, parent_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        raise NotImplementedError

    async def get_tree(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        raise NotImplementedError

    async def update(self, wbs_id: UUID, wbs_item: WBSItem, tenant_id: UUID) -> WBSItem | None:
        raise NotImplementedError

    async def delete(self, wbs_id: UUID, tenant_id: UUID) -> bool:
        raise NotImplementedError


@pytest.mark.asyncio
class TestWBSProcurementIntegration:
    """Refers to Suite ID: TS-INT-MOD-WBS-001."""

    async def test_import_maps_wbs_items_and_persists(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        parent_id = uuid4()

        dtos = [
            WBSItemDTO(
                id=parent_id,
                project_id=project_id,
                code="1",
                name="Project Root",
                level=1,
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 15),
                specifications={"discipline": "general"},
            ),
            WBSItemDTO(
                id=uuid4(),
                project_id=project_id,
                code="1.1",
                name="Civil Works",
                level=2,
                start_date=date(2026, 2, 16),
                end_date=date(2026, 3, 1),
                parent_id=parent_id,
            ),
        ]

        repo = _FakeWBSRepository()
        use_case = ImportWBSFromProjectsUseCase(repo)

        result = await use_case.execute(project_id=project_id, tenant_id=tenant_id, items=dtos)

        assert len(result) == 2
        assert len(repo.created_items) == 2
        assert repo.created_items[0].project_id == project_id
        assert repo.created_items[0].code == "1"
        assert repo.created_items[0].name == "Project Root"
        assert repo.created_items[0].level == 1
        assert repo.created_items[0].wbs_metadata["discipline"] == "general"
        assert repo.created_items[1].wbs_metadata["parent_id"] == str(parent_id)

    async def test_import_raises_on_project_mismatch(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()

        dtos = [
            WBSItemDTO(
                id=uuid4(),
                project_id=uuid4(),
                code="1",
                name="Invalid",
                level=1,
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 2),
            )
        ]

        use_case = ImportWBSFromProjectsUseCase(_FakeWBSRepository())

        with pytest.raises(ValueError):
            await use_case.execute(project_id=project_id, tenant_id=tenant_id, items=dtos)
