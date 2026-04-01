"""
I9 - Procurement HTTP dependency injection contracts.
Test Suite ID: TS-I9-PROC-HTTP-001
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.procurement.adapters.http.router import (
    get_create_bom_item_use_case,
    get_create_wbs_item_use_case,
    get_planning_service,
    router,
)
from src.procurement.application.dtos import PlanningDecision
from src.procurement.domain.models import ProcurementStatus
from src.core.security import get_current_tenant_id


class _FakePlanningSnapshotRepository:
    async def get_snapshot_items(self, project_id: UUID, tenant_id: UUID, required_on_site: datetime):
        raise AssertionError("not used by this test")


class _FakePlanningDecisionRepository:
    async def save_plan_items(self, project_id: UUID, tenant_id: UUID, items):
        raise AssertionError("not used by this test")

    async def save_conflicts(self, project_id: UUID, tenant_id: UUID, conflicts):
        raise AssertionError("not used by this test")


class _FakePlanningUnitOfWork:
    async def commit(self) -> None:
        raise AssertionError("not used by this test")

    async def rollback(self) -> None:
        raise AssertionError("not used by this test")


class _FakeCreateWBSUseCase:
    async def execute(self, wbs_create, tenant_id: UUID):
        return SimpleNamespace(
            id=uuid4(),
            project_id=wbs_create.project_id,
            parent_id=wbs_create.parent_id,
            wbs_code=wbs_create.wbs_code,
            name="Injected WBS",
            description=wbs_create.description,
            level=wbs_create.level,
            item_type=wbs_create.item_type,
            budget_allocated=wbs_create.budget_allocated,
            budget_spent=wbs_create.budget_spent,
            planned_start=wbs_create.planned_start,
            planned_end=wbs_create.planned_end,
            actual_start=wbs_create.actual_start,
            actual_end=wbs_create.actual_end,
            wbs_metadata=wbs_create.wbs_metadata,
            funded_by_clause_id=wbs_create.funded_by_clause_id,
            children=[],
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            updated_at=datetime(2026, 1, 1, 12, 0, 0),
        )


class _FakeCreateBOMUseCase:
    async def execute(self, bom_create, tenant_id: UUID):
        return SimpleNamespace(
            id=uuid4(),
            project_id=bom_create.project_id,
            wbs_item_id=bom_create.wbs_item_id,
            item_code=bom_create.item_code,
            item_name="Injected BOM",
            description=bom_create.description,
            category=bom_create.category,
            quantity=bom_create.quantity,
            unit=bom_create.unit,
            unit_price=bom_create.unit_price,
            total_price=bom_create.total_price,
            currency=bom_create.currency,
            supplier=bom_create.supplier,
            lead_time_days=bom_create.lead_time_days,
            incoterm=bom_create.incoterm,
            procurement_status=bom_create.procurement_status,
            bom_metadata=bom_create.bom_metadata,
            contract_clause_id=bom_create.contract_clause_id,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            updated_at=datetime(2026, 1, 1, 12, 0, 0),
        )


def test_i9_planning_service_provider_uses_injected_collaborators() -> None:
    """TS-I9-PROC-HTTP-001: planning provider must compose the service from injected collaborators."""
    snapshot_repo = _FakePlanningSnapshotRepository()
    decision_repo = _FakePlanningDecisionRepository()
    uow = _FakePlanningUnitOfWork()

    service = get_planning_service(
        repository=snapshot_repo,
        decision_repository=decision_repo,
        uow=uow,
    )

    assert service.repository is snapshot_repo
    assert service.decision_repository is decision_repo
    assert service.uow is uow


@pytest.mark.asyncio
async def test_i9_create_wbs_endpoint_uses_dependency_override() -> None:
    """TS-I9-PROC-HTTP-001: WBS create route must use an overridable use case dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    app.dependency_overrides[get_create_wbs_item_use_case] = lambda: _FakeCreateWBSUseCase()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/procurement/wbs",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "wbs_code": "1.1",
                "name": "Concrete Works",
                "level": 1,
                "budget_spent": "0",
                "wbs_metadata": {},
            },
        )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Injected WBS"


@pytest.mark.asyncio
async def test_i9_create_bom_endpoint_uses_dependency_override() -> None:
    """TS-I9-PROC-HTTP-001: BOM create route must use an overridable use case dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    app.dependency_overrides[get_create_bom_item_use_case] = lambda: _FakeCreateBOMUseCase()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/procurement/bom",
            json={
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "item_name": "Cable Tray",
                "quantity": str(Decimal("2")),
                "currency": "EUR",
                "procurement_status": ProcurementStatus.PENDING.value,
                "bom_metadata": {},
            },
        )

    assert response.status_code == 201, response.text
    assert response.json()["item_name"] == "Injected BOM"
