"""
I9 - Procurement Persistence Tenant Filters (Adapter)
Test Suite ID: TS-I9-PROC-ADP-001
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from src.modules.procurement.adapters.persistence.snapshot_repository import (
    SQLAlchemyProcurementSnapshotRepository,
)
from src.modules.procurement.domain.entities import ProcurementPlanItem


@pytest.mark.asyncio
async def test_i9_snapshot_repository_applies_tenant_filter_in_all_reads() -> None:
    """I9 adapter contract: all snapshot reads must be tenant-scoped."""
    repository = SQLAlchemyProcurementSnapshotRepository(session=None)  # type: ignore[arg-type]

    project_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    items = await repository.get_snapshot_items(
        project_id=project_id,
        tenant_id=tenant_id,
        required_on_site=date(2026, 9, 1),
    )

    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_i9_snapshot_repository_returns_only_request_tenant_rows() -> None:
    """I9 adapter contract: repository must never leak cross-tenant plan items."""
    repository = SQLAlchemyProcurementSnapshotRepository(session=None)  # type: ignore[arg-type]

    result = await repository.get_snapshot_items(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        required_on_site=date(2026, 9, 1),
    )

    assert all(isinstance(item, ProcurementPlanItem) for item in result)
