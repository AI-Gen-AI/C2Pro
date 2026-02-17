"""
I9 - Procurement Pipeline Integration
Test Suite ID: TS-I9-PROC-INT-001
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

from src.modules.procurement.application.integration import ProcurementPipelineIntegrationService


@pytest.mark.asyncio
async def test_i9_pipeline_builds_procurement_plan_from_wbs_bom_snapshot_with_traceability() -> None:
    """
    I9 integration contract:
    WBS/BOM snapshot must produce procurement plan with source traceability links.
    """
    service = ProcurementPipelineIntegrationService()
    project_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    decision = await service.build_from_wbs_bom_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        required_on_site=date(2026, 9, 1),
    )

    assert decision.plan_fingerprint
    assert len(decision.plan_items) > 0
    assert all(item.get("source_wbs_id") for item in decision.plan_items)
    assert all(item.get("source_bom_id") for item in decision.plan_items)


@pytest.mark.asyncio
async def test_i9_pipeline_rejects_cross_tenant_snapshot_rows() -> None:
    """
    I9 integration contract:
    mixed-tenant snapshot data must be blocked and fail fast.
    """
    service = ProcurementPipelineIntegrationService()

    with pytest.raises(ValueError, match="cross-tenant snapshot"):
        await service.build_from_wbs_bom_snapshot(
            project_id=uuid4(),
            tenant_id=uuid4(),
            required_on_site=date(2026, 9, 1),
        )
