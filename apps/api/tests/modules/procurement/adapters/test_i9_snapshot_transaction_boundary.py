"""
I9 - Snapshot Transaction Boundary (Adapter)
Test Suite ID: TS-I9-PROC-ADP-002
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.procurement.adapters.persistence.snapshot_repository import (
    SQLAlchemyProcurementDecisionRepository,
)
from src.procurement.domain.models import ProcurementPlanItem, ProcurementPriority


@pytest.mark.asyncio
async def test_i9_adp_txn_rolls_back_when_second_write_fails_red() -> None:
    """TS-I9-PROC-ADP-002: second write failure must rollback full transaction boundary."""
    session = AsyncMock()
    repo = SQLAlchemyProcurementDecisionRepository(session=session)
    items = [
        ProcurementPlanItem(
            bom_item_id=UUID("11111111-1111-1111-1111-111111111111"),
            item_name="Primary Switchgear",
            quantity=Decimal("1"),
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 20),
            total_cost=Decimal("150000.00"),
            priority=ProcurementPriority.MEDIUM,
        )
    ]
    conflicts = [{"reason_code": "LATE_ORDER_WINDOW", "impact": "HIGH"}]

    session.execute.side_effect = [None, RuntimeError("conflict insert failed")]

    with pytest.raises(RuntimeError, match="conflict insert failed"):
        await repo.persist_decision_atomic(
            project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            plan_items=items,
            conflicts=conflicts,
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_i9_adp_txn_idempotent_retry_does_not_duplicate_rows_red() -> None:
    """TS-I9-PROC-ADP-002: retry with same fingerprint must not duplicate persisted rows."""
    session = AsyncMock()
    repo = SQLAlchemyProcurementDecisionRepository(session=session)
    items = [
        ProcurementPlanItem(
            bom_item_id=UUID("11111111-1111-1111-1111-111111111111"),
            item_name="Primary Switchgear",
            quantity=Decimal("1"),
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 20),
            total_cost=Decimal("150000.00"),
            priority=ProcurementPriority.MEDIUM,
        )
    ]
    conflicts = [{"reason_code": "LATE_ORDER_WINDOW", "impact": "HIGH"}]

    await repo.persist_decision_atomic(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        plan_items=items,
        conflicts=conflicts,
        fingerprint="f" * 64,
    )
    await repo.persist_decision_atomic(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        plan_items=items,
        conflicts=conflicts,
        fingerprint="f" * 64,
    )

    # Contract: same fingerprint is idempotent and must not produce a second commit.
    session.rollback.assert_not_awaited()
    session.commit.assert_awaited_once()
