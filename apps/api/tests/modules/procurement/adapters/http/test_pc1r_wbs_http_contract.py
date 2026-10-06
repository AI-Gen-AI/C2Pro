"""PC-1R WBS HTTP + use-case contract (TS-PC1R-WBS-HTTP-001).

The structural guarantees run against real PostgreSQL in
tests/modules/integration/test_pc1r_wbs_structural_integrity.py. This suite pins how
they surface to clients: a linked delete is a 409 ``WBS_NODE_HAS_LINKS`` (never a raw
500), an invalid parent is a 422, and an update forwards recode / reparent / position
to the repository without touching the node's identity.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.handlers import register_exception_handlers
from src.core.security import get_current_tenant_id
from src.procurement.adapters.http.router import (
    get_create_wbs_item_use_case,
    get_delete_wbs_item_use_case,
    get_update_wbs_item_use_case,
    router,
)
from src.procurement.adapters.persistence.wbs_repository import WBSNodeLinkedError
from src.procurement.application.dtos import WBSItemUpdate
from src.procurement.application.use_cases.wbs_use_cases import UpdateWBSItemUseCase
from src.procurement.domain.models import WBSItem, WBSItemType

TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class _Raises:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def execute(self, *args: Any) -> Any:  # noqa: ARG002 - HTTP contract fake
        raise self.error


def _app(dependency: Callable[..., Any], use_case: Any) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: TENANT
    # No default-argument lambda: FastAPI would treat it as a parameter and deep-copy the fake.
    app.dependency_overrides[dependency] = lambda: use_case
    return app


async def _call(app: FastAPI, method: str, url: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        return await client.request(method, url, headers={"X-Tenant-Id": str(TENANT)}, **kwargs)


@pytest.mark.asyncio
async def test_deleting_a_linked_node_is_a_409_with_link_counts() -> None:
    wbs_id = uuid4()
    app = _app(get_delete_wbs_item_use_case, _Raises(WBSNodeLinkedError(wbs_id, raci_links=2, bom_links=1)))

    response = await _call(app, "DELETE", f"/api/v1/procurement/wbs/{wbs_id}")

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error_code"] == "WBS_NODE_HAS_LINKS"
    assert "2 RACI" in body["message"] and "1 BOM" in body["message"]


@pytest.mark.asyncio
async def test_create_with_a_parent_outside_the_project_is_a_422() -> None:
    app = _app(get_create_wbs_item_use_case, _Raises(ValueError("Parent WBS item is not in this project")))

    response = await _call(
        app,
        "POST",
        "/api/v1/procurement/wbs",
        json={"project_id": str(uuid4()), "parent_id": str(uuid4()), "wbs_code": "1.1", "name": "Civil", "level": 2},
    )

    assert response.status_code == 422, response.text
    assert "not in this project" in response.text


@pytest.mark.asyncio
async def test_create_passes_domain_conflicts_through_unchanged() -> None:
    app = _app(get_create_wbs_item_use_case, _Raises(WBSNodeLinkedError(uuid4(), raci_links=1, bom_links=0)))

    response = await _call(
        app,
        "POST",
        "/api/v1/procurement/wbs",
        json={"project_id": str(uuid4()), "wbs_code": "1", "name": "Civil", "level": 1},
    )

    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_update_into_its_own_subtree_is_a_422() -> None:
    app = _app(
        get_update_wbs_item_use_case, _Raises(ValueError("A WBS item cannot be moved under itself or its descendants"))
    )

    response = await _call(app, "PUT", f"/api/v1/procurement/wbs/{uuid4()}", json={"parent_id": str(uuid4())})

    assert response.status_code == 422, response.text
    assert "descendants" in response.text


class _UpdateRepository:
    def __init__(self, existing: WBSItem) -> None:
        self.existing = existing
        self.updated: list[tuple[UUID, WBSItem, UUID]] = []

    async def get_by_id(self, wbs_id: UUID, tenant_id: UUID) -> WBSItem | None:  # noqa: ARG002
        return self.existing if wbs_id == self.existing.id else None

    async def update(self, wbs_id: UUID, wbs_item: WBSItem, tenant_id: UUID) -> WBSItem:
        self.updated.append((wbs_id, wbs_item, tenant_id))
        return wbs_item


def _item() -> WBSItem:
    return WBSItem(project_id=uuid4(), code="1.2", name="Civil", level=2, item_type=WBSItemType.WORK_PACKAGE)


@pytest.mark.asyncio
async def test_update_forwards_recode_reparent_and_position_keeping_identity() -> None:
    existing = _item()
    new_parent = uuid4()
    repository = _UpdateRepository(existing)

    result = await UpdateWBSItemUseCase(repository).execute(
        existing.id, WBSItemUpdate(wbs_code="2.7", parent_id=new_parent, sort_order=3), TENANT
    )

    assert result is not None
    [(wbs_id, item, tenant)] = repository.updated
    assert (wbs_id, item.id, tenant) == (existing.id, existing.id, TENANT)
    assert (item.code, item.parent_id, item.sort_order) == ("2.7", new_parent, 3)


@pytest.mark.asyncio
async def test_update_without_structural_fields_leaves_code_parent_and_position_alone() -> None:
    existing = _item()
    existing.parent_id, existing.sort_order = uuid4(), 4
    before = (existing.code, existing.parent_id, existing.sort_order)
    repository = _UpdateRepository(existing)

    await UpdateWBSItemUseCase(repository).execute(existing.id, WBSItemUpdate(name="Civil works"), TENANT)

    [(_, item, _)] = repository.updated
    assert (item.code, item.parent_id, item.sort_order) == before
    assert item.name == "Civil works"


@pytest.mark.asyncio
async def test_update_of_an_unknown_node_does_not_write() -> None:
    repository = _UpdateRepository(_item())

    assert await UpdateWBSItemUseCase(repository).execute(uuid4(), WBSItemUpdate(wbs_code="9"), TENANT) is None
    assert repository.updated == []
