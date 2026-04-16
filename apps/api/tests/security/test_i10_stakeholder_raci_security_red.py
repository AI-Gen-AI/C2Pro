from datetime import timezone
"""
I10 stakeholder + RACI security hardening tests (RED).
Test Suite ID: TS-I10-STK-SEC-001
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.stakeholders.application.dtos import RaciGenerationAssignment, RaciGenerationResult
from src.stakeholders.application.services.raci_generation_service import RaciGenerationService
from src.stakeholders.domain.models import InterestLevel, PowerLevel, RACIRole, Stakeholder


def _stakeholder(project_id, stakeholder_id) -> Stakeholder:
    now = datetime.now(timezone.utc)
    return Stakeholder(
        id=stakeholder_id,
        project_id=project_id,
        power_level=PowerLevel.HIGH,
        interest_level=InterestLevel.HIGH,
        approval_status="approved",
        created_at=now,
        updated_at=now,
        name="Contractor Inc.",
        role="Contractor",
        organization="BuildCo",
        stakeholder_metadata={"type": "external"},
    )


def _wbs_row(*, wbs_item_id, clause_id):
    return SimpleNamespace(
        id=wbs_item_id,
        code="1.1.1",
        parent_code=None,
        name="Structural Works",
        description="Execute structural package",
        source_clause_id=clause_id,
    )


@pytest.mark.asyncio
async def test_i10_sec_ambiguity_requires_hitl_and_blocks_auto_persist_red() -> None:
    """
    TS-I10-STK-SEC-001:
    ambiguous stakeholder mappings must block auto-persistence until HITL review.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    stakeholder_id = uuid4()
    wbs_item_id = uuid4()
    clause_id = uuid4()

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = (
        [_stakeholder(project_id, stakeholder_id)],
        1,
    )
    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [_wbs_row(wbs_item_id=wbs_item_id, clause_id=clause_id)]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {
        clause_id: "The Client shall approve payment certificates."
    }
    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(
        assignments=[
            RaciGenerationAssignment(
                wbs_item_id=wbs_item_id,
                stakeholder_id=stakeholder_id,
                role=RACIRole.ACCOUNTABLE,
                evidence_text="Clause evidence",
            )
        ],
        warnings=[],
    )
    stakeholder_repository = AsyncMock()
    stakeholder_repository.list_raci_assignments.return_value = []
    inference_gateway = AsyncMock()
    inference_gateway.generate_raci_matrix.return_value = (
        [],
        [{"entity_name": "Client Holdings", "reason": "ambiguous_mapping"}],
    )

    service = RaciGenerationService(
        tenant_id=tenant_id,
        list_stakeholders_use_case=list_stakeholders_use_case,
        wbs_repository=wbs_repository,
        document_repository=document_repository,
        raci_generator=raci_generator,
        stakeholder_repository=stakeholder_repository,
        raci_inference_service=inference_gateway,
    )

    with pytest.raises(ValueError, match="requires PMO/legal validation"):
        await service.generate_and_persist(project_id)

    stakeholder_repository.add_raci_assignment.assert_not_awaited()
    stakeholder_repository.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_i10_sec_repository_reads_are_tenant_scoped_for_raci_assignments_red() -> None:
    """
    TS-I10-STK-SEC-001:
    assignment reads must pass tenant_id to prevent cross-tenant leakage.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    stakeholder_id = uuid4()
    wbs_item_id = uuid4()
    clause_id = uuid4()

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = (
        [_stakeholder(project_id, stakeholder_id)],
        1,
    )
    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [_wbs_row(wbs_item_id=wbs_item_id, clause_id=clause_id)]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {clause_id: "Clause text"}
    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(
        assignments=[
            RaciGenerationAssignment(
                wbs_item_id=wbs_item_id,
                stakeholder_id=stakeholder_id,
                role=RACIRole.RESPONSIBLE,
                evidence_text="Clause evidence",
            )
        ],
        warnings=[],
    )
    stakeholder_repository = AsyncMock()
    stakeholder_repository.list_raci_assignments.return_value = []

    service = RaciGenerationService(
        tenant_id=tenant_id,
        list_stakeholders_use_case=list_stakeholders_use_case,
        wbs_repository=wbs_repository,
        document_repository=document_repository,
        raci_generator=raci_generator,
        stakeholder_repository=stakeholder_repository,
    )

    await service.generate_and_persist(project_id)

    stakeholder_repository.list_raci_assignments.assert_awaited_once_with(
        project_id,
        tenant_id=tenant_id,
    )


@pytest.mark.asyncio
async def test_i10_sec_persistence_errors_are_sanitized_before_surface_red() -> None:
    """
    TS-I10-STK-SEC-001:
    security-sensitive persistence failures must be surfaced with sanitized error messages.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    known_stakeholder_id = uuid4()
    unknown_stakeholder_id = uuid4()
    wbs_item_id = uuid4()
    clause_id = uuid4()

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = (
        [_stakeholder(project_id, known_stakeholder_id)],
        1,
    )
    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [_wbs_row(wbs_item_id=wbs_item_id, clause_id=clause_id)]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {clause_id: "Clause text"}
    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(
        assignments=[
            RaciGenerationAssignment(
                wbs_item_id=wbs_item_id,
                stakeholder_id=unknown_stakeholder_id,
                role=RACIRole.CONSULTED,
                evidence_text="Clause evidence",
            )
        ],
        warnings=[],
    )
    stakeholder_repository = AsyncMock()
    stakeholder_repository.list_raci_assignments.return_value = []

    service = RaciGenerationService(
        tenant_id=tenant_id,
        list_stakeholders_use_case=list_stakeholders_use_case,
        wbs_repository=wbs_repository,
        document_repository=document_repository,
        raci_generator=raci_generator,
        stakeholder_repository=stakeholder_repository,
    )

    with pytest.raises(ValueError, match="unable to persist raci assignments"):
        await service.generate_and_persist(project_id)
