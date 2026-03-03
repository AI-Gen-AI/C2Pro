"""
I9 - Procurement Transactional Atomicity (Application)
Test Suite ID: TS-I9-PROC-TXN-001
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.modules.procurement.application.ports import (
    ProcurementPlanningService,
    ProcurementSnapshotRepository,
)
from src.modules.procurement.domain.entities import ProcurementPlanItem


@pytest.fixture
def snapshot_repository() -> AsyncMock:
    repo = AsyncMock(spec=ProcurementSnapshotRepository)
    repo.get_snapshot_items.return_value = [
        ProcurementPlanItem(
            item_name="Primary Switchgear",
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 20),
            total_cost=Decimal("150000.00"),
        )
    ]
    return repo


@pytest.mark.asyncio
async def test_i9_txn_rolls_back_when_conflict_persistence_fails_red(
    snapshot_repository: AsyncMock,
) -> None:
    """
    TS-I9-PROC-TXN-001:
    If persistence of conflicts fails, service must rollback and never commit partial state.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.side_effect = RuntimeError("conflict persist failed")
    uow = AsyncMock()

    service = ProcurementPlanningService(
        repository=snapshot_repository,
        decision_repository=decision_repository,
        uow=uow,
    )

    with pytest.raises(RuntimeError, match="conflict persist failed"):
        await service.build_and_persist_procurement_plan(
            project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            required_on_site=date(2026, 9, 1),
        )

    decision_repository.save_plan_items.assert_awaited_once()
    decision_repository.save_conflicts.assert_awaited_once()
    uow.commit.assert_not_awaited()
    uow.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_i9_txn_rolls_back_when_commit_fails_red(
    snapshot_repository: AsyncMock,
) -> None:
    """
    TS-I9-PROC-TXN-001:
    If commit fails after staged writes, service must trigger rollback and bubble a controlled error.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.return_value = None
    uow = AsyncMock()
    uow.commit.side_effect = RuntimeError("commit failed")

    service = ProcurementPlanningService(
        repository=snapshot_repository,
        decision_repository=decision_repository,
        uow=uow,
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.build_and_persist_procurement_plan(
            project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            required_on_site=date(2026, 9, 1),
        )

    decision_repository.save_plan_items.assert_awaited_once()
    decision_repository.save_conflicts.assert_awaited_once()
    uow.commit.assert_awaited_once()
    uow.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_i9_txn_retry_same_fingerprint_is_idempotent_red(
    snapshot_repository: AsyncMock,
) -> None:
    """
    TS-I9-PROC-TXN-001:
    retrying the same transactional request fingerprint must not duplicate staged writes.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.return_value = None
    uow = AsyncMock()

    service = ProcurementPlanningService(
        repository=snapshot_repository,
        decision_repository=decision_repository,
        uow=uow,
    )

    await service.build_and_persist_procurement_plan(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        required_on_site=date(2026, 9, 1),
        fingerprint="f" * 64,
    )
    await service.build_and_persist_procurement_plan(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        required_on_site=date(2026, 9, 1),
        fingerprint="f" * 64,
    )

    decision_repository.save_plan_items.assert_awaited_once()
    decision_repository.save_conflicts.assert_awaited_once()
    uow.commit.assert_awaited_once()
    uow.rollback.assert_not_awaited()
