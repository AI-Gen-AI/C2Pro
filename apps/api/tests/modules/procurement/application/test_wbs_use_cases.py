"""
Unit tests for procurement WBS use cases.
Refers to Suite ID: TS-UD-DOC-EXT-002.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.procurement.application.dtos import WBSItemCreate
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.procurement.domain.models import WBSItem, WBSItemType


class _FakeWBSRepository:
    def __init__(self, existing: WBSItem | None = None) -> None:
        self.existing = existing
        self.created: list[WBSItem] = []
        self.updated: list[tuple] = []
        self.replaced: dict | None = None

    async def get_by_code(self, project_id, wbs_code, tenant_id):
        if self.existing and self.existing.project_id == project_id and self.existing.code == wbs_code:
            return self.existing
        return None

    async def get_by_id(self, wbs_id, tenant_id):
        return None

    async def create(self, wbs_item, tenant_id):
        self.created.append(wbs_item)
        return wbs_item

    async def update(self, wbs_id, wbs_item, tenant_id):
        self.updated.append((wbs_id, wbs_item, tenant_id))
        return wbs_item

    async def replace_for_source_document(
        self, *, project_id, source_document_id, wbs_items, tenant_id
    ):
        self.replaced = {
            "project_id": project_id,
            "source_document_id": source_document_id,
            "wbs_items": wbs_items,
            "tenant_id": tenant_id,
        }
        return wbs_items


@pytest.mark.asyncio
async def test_replace_for_source_document_maps_dtos_and_scopes_to_document() -> None:
    """TS-UD-PROC-WBS-IDEM-001: the use case maps DTOs to domain WBS items stamped with the source document."""
    project_id = uuid4()
    tenant_id = uuid4()
    document_id = uuid4()
    repo = _FakeWBSRepository()
    use_case = CreateWBSItemUseCase(repo)

    result = await use_case.replace_for_source_document(
        project_id=project_id,
        source_document_id=document_id,
        wbs_items=[
            WBSItemCreate(
                project_id=project_id,
                wbs_code="SCH-001",
                name="Mobilization",
                level=1,
                item_type=WBSItemType.ACTIVITY,
                wbs_metadata={"predecessor_id": "SCH-000"},
            ),
        ],
        tenant_id=tenant_id,
    )

    assert repo.replaced is not None
    assert repo.replaced["project_id"] == project_id
    assert repo.replaced["source_document_id"] == document_id
    assert repo.replaced["tenant_id"] == tenant_id
    built = repo.replaced["wbs_items"]
    assert [item.code for item in built] == ["SCH-001"]
    assert built[0].source_document_id == document_id
    # source document stamped into metadata; caller-supplied keys preserved.
    assert built[0].wbs_metadata["source_document_id"] == str(document_id)
    assert built[0].wbs_metadata["predecessor_id"] == "SCH-000"
    assert result == built


@pytest.mark.asyncio
async def test_i12_schedule_derived_activity_projection_is_idempotent_for_same_source_document() -> None:
    """TS-UD-DOC-EXT-002: re-parsing one schedule updates only its generated activity projection."""
    project_id = uuid4()
    tenant_id = uuid4()
    document_id = uuid4()
    existing = WBSItem(
        project_id=project_id,
        code="1.0",
        name="Old schedule task",
        level=2,
        item_type=WBSItemType.ACTIVITY,
        wbs_metadata={"source_document_id": str(document_id)},
    )
    repo = _FakeWBSRepository(existing=existing)
    use_case = CreateWBSItemUseCase(repo)

    result = await use_case.execute(
        WBSItemCreate(
            project_id=project_id,
            wbs_code="1.0",
            name="Gestión del contrato",
            level=2,
            item_type=WBSItemType.ACTIVITY,
            wbs_metadata={"source_document_id": str(document_id)},
        ),
        tenant_id,
    )

    assert result.name == "Gestión del contrato"
    assert repo.created == []
    assert len(repo.updated) == 1
    assert repo.updated[0][0] == existing.id
