"""
I9 - Procurement Pipeline Atomicity Integration
Test Suite ID: TS-I9-PROC-INT-002
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.procurement.application.integration_service import ProcurementPipelineIntegrationService


@pytest.mark.asyncio
async def test_i9_int_pipeline_rolls_back_and_prevents_partial_write_on_persist_failure_red() -> None:
    """
    TS-I9-PROC-INT-002:
    integrated WBS/BOM -> procurement pipeline must rollback when persistence fails after staging.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.side_effect = RuntimeError("conflict persist failed")
    uow = AsyncMock()

    service = ProcurementPipelineIntegrationService(
        decision_repository=decision_repository,
        uow=uow,
    )

    with pytest.raises(RuntimeError, match="conflict persist failed"):
        await service.build_and_persist_from_wbs_bom_snapshot(
            project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            required_on_site=date(2026, 9, 1),
        )

    decision_repository.save_plan_items.assert_awaited_once()
    decision_repository.save_conflicts.assert_awaited_once()
    uow.commit.assert_not_awaited()
    uow.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_i9_int_pipeline_retry_same_fingerprint_is_idempotent_red() -> None:
    """
    TS-I9-PROC-INT-002:
    retrying the same integrated request fingerprint must not duplicate persisted rows.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.return_value = None
    uow = AsyncMock()

    service = ProcurementPipelineIntegrationService(
        decision_repository=decision_repository,
        uow=uow,
    )

    await service.build_and_persist_from_wbs_bom_snapshot(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        required_on_site=date(2026, 9, 1),
        fingerprint="f" * 64,
    )
    await service.build_and_persist_from_wbs_bom_snapshot(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        required_on_site=date(2026, 9, 1),
        fingerprint="f" * 64,
    )

    decision_repository.save_plan_items.assert_awaited_once()
    decision_repository.save_conflicts.assert_awaited_once()
    uow.commit.assert_awaited_once()
    uow.rollback.assert_not_awaited()
