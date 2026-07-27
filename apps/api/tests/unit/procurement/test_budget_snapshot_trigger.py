"""Baseline-change snapshot trigger tests for procurement budgets.

Test Suite ID: TS-UT-PROC-BASELINE-SNAPSHOT-001
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.core.tenants.types import TenantId
from src.procurement.application.budget_use_cases import (
    BudgetItemCreate,
    BudgetItemUpdate,
    CreateBudgetItemUseCase,
    DeleteBudgetItemUseCase,
    UpdateBudgetItemUseCase,
)


class _BudgetRepository:
    async def create(self, **kwargs: Any) -> dict[str, object]:
        return {
            "id": uuid4(),
            "project_id": kwargs["project_id"],
            "name": kwargs["name"],
            "code": kwargs["code"],
            "amount": kwargs["amount"],
        }

    async def update(self, item_id: UUID, tenant_id: TenantId, **kwargs: Any) -> dict[str, object]:
        return {
            "id": item_id,
            "project_id": self.project_id,
            "name": kwargs.get("name", "Baseline"),
            "code": kwargs.get("code", "BASE-001"),
            "amount": kwargs.get("amount", Decimal("100.00")),
        }

    async def get_by_id(self, item_id: UUID, tenant_id: TenantId) -> dict[str, object]:
        return {"id": item_id, "project_id": self.project_id}

    async def delete(self, item_id: UUID, tenant_id: TenantId) -> bool:
        return True


@pytest.mark.asyncio
async def test_explicit_baseline_change_emits_tenant_scoped_snapshot_trigger(monkeypatch) -> None:
    """TS-UT-PROC-BASELINE-SNAPSHOT-001: ordinary CRUD is not inferred as a baseline change."""
    from src.procurement.application import budget_use_cases

    project_id = uuid4()
    tenant_id = TenantId(uuid4())
    calls: list[dict[str, Any]] = []

    async def fake_record_trigger(**kwargs: Any) -> UUID:
        calls.append(kwargs)
        return uuid4()

    monkeypatch.setattr(
        budget_use_cases,
        "record_project_event_and_enqueue_snapshot",
        fake_record_trigger,
        raising=False,
    )

    result = await CreateBudgetItemUseCase(_BudgetRepository()).execute(
        project_id=project_id,
        tenant_id=tenant_id,
        data=BudgetItemCreate(
            name="Approved baseline",
            code="BASE-001",
            amount=Decimal("100.00"),
            is_baseline_change=True,
        ),
    )

    assert result.project_id == project_id
    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "event_type": "baseline.changed",
            "payload": {
                "action": "created",
                "budget_item_id": str(result.id),
            },
            "trigger": budget_use_cases.SnapshotTrigger.BASELINE_CHANGED,
            "actor": "procurement_budget",
        }
    ]


@pytest.mark.asyncio
async def test_ordinary_budget_edit_does_not_infer_a_baseline_change(monkeypatch) -> None:
    """TS-UT-PROC-BASELINE-SNAPSHOT-001: baseline snapshots require explicit intent."""
    from src.procurement.application import budget_use_cases

    calls: list[dict[str, Any]] = []

    async def fake_record_trigger(**kwargs: Any) -> UUID:
        calls.append(kwargs)
        return uuid4()

    monkeypatch.setattr(
        budget_use_cases,
        "record_project_event_and_enqueue_snapshot",
        fake_record_trigger,
        raising=False,
    )

    await CreateBudgetItemUseCase(_BudgetRepository()).execute(
        project_id=uuid4(),
        tenant_id=TenantId(uuid4()),
        data=BudgetItemCreate(name="Working estimate", code="EST-001", amount=Decimal("25.00")),
    )

    assert calls == []


@pytest.mark.asyncio
async def test_baseline_snapshot_failure_does_not_block_budget_mutation(monkeypatch) -> None:
    """TS-UT-PROC-BASELINE-SNAPSHOT-001: snapshot infrastructure is fail-open."""
    from src.procurement.application import budget_use_cases

    async def failing_record_trigger(**_kwargs: Any) -> UUID:
        raise RuntimeError("temporal store unavailable")

    monkeypatch.setattr(
        budget_use_cases,
        "record_project_event_and_enqueue_snapshot",
        failing_record_trigger,
        raising=False,
    )

    response = await CreateBudgetItemUseCase(_BudgetRepository()).execute(
        project_id=uuid4(),
        tenant_id=TenantId(uuid4()),
        data=BudgetItemCreate(
            name="Approved baseline",
            code="BASE-002",
            amount=Decimal("100.00"),
            is_baseline_change=True,
        ),
    )

    assert response.code == "BASE-002"


@pytest.mark.asyncio
async def test_explicit_baseline_update_and_delete_emit_snapshot_triggers(monkeypatch) -> None:
    """TS-UT-PROC-BASELINE-SNAPSHOT-001: every explicit baseline mutation is captured."""
    from src.procurement.application import budget_use_cases

    project_id = uuid4()
    tenant_id = TenantId(uuid4())
    item_id = uuid4()
    repository = _BudgetRepository()
    repository.project_id = project_id
    calls: list[dict[str, Any]] = []

    async def fake_record_trigger(**kwargs: Any) -> UUID:
        calls.append(kwargs)
        return uuid4()

    monkeypatch.setattr(
        budget_use_cases,
        "record_project_event_and_enqueue_snapshot",
        fake_record_trigger,
        raising=False,
    )

    await UpdateBudgetItemUseCase(repository).execute(
        item_id=item_id,
        tenant_id=tenant_id,
        data=BudgetItemUpdate(amount=Decimal("125.00"), is_baseline_change=True),
    )
    await DeleteBudgetItemUseCase(repository).execute(
        item_id=item_id,
        tenant_id=tenant_id,
        is_baseline_change=True,
    )

    assert [call["payload"]["action"] for call in calls] == ["updated", "deleted"]
    assert all(call["tenant_id"] == tenant_id for call in calls)
    assert all(call["project_id"] == project_id for call in calls)
