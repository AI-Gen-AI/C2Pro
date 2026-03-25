"""
I9 - Procurement Atomicity Security Hardening (RED)
Test Suite ID: TS-SEC-I9-002
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.procurement.application.integration_service import ProcurementPipelineIntegrationService


@pytest.mark.asyncio
async def test_sec_i9_txn_failure_message_is_sanitized_red() -> None:
    """
    TS-SEC-I9-002:
    transactional failures must be sanitized and never leak infrastructure or tenant details.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.side_effect = RuntimeError(
        "db timeout on shard=tenant-bbbb, replica=10.0.0.8, tx=deadbeef"
    )
    uow = AsyncMock()
    service = ProcurementPipelineIntegrationService(
        decision_repository=decision_repository,
        uow=uow,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await service.build_and_persist_from_wbs_bom_snapshot(
            project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            required_on_site=date(2026, 9, 1),
            fingerprint="f" * 64,
        )

    error_text = str(exc_info.value).lower()
    assert "tenant-bbbb" not in error_text
    assert "10.0.0.8" not in error_text
    assert "deadbeef" not in error_text


@pytest.mark.asyncio
async def test_sec_i9_txn_failure_does_not_expose_partial_state_markers_red() -> None:
    """
    TS-SEC-I9-002:
    when rollback is triggered, error paths must not expose partial-write state markers.
    """
    decision_repository = AsyncMock()
    decision_repository.save_plan_items.return_value = None
    decision_repository.save_conflicts.side_effect = RuntimeError(
        "partial write detected: source_wbs_id=11111111-1111-1111-1111-111111111111"
        " source_bom_id=22222222-2222-2222-2222-222222222222"
        " fingerprint=ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    )
    uow = AsyncMock()
    service = ProcurementPipelineIntegrationService(
        decision_repository=decision_repository,
        uow=uow,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await service.build_and_persist_from_wbs_bom_snapshot(
            project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            required_on_site=date(2026, 9, 1),
            fingerprint="f" * 64,
        )

    error_text = str(exc_info.value).lower()
    assert "source_wbs_id" not in error_text
    assert "source_bom_id" not in error_text
    assert "fingerprint" not in error_text
