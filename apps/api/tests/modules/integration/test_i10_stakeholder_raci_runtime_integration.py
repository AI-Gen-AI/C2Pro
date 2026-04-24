
"""
I10 - Stakeholder Runtime Wiring Integration (RED)
Test Suite ID: TS-I10-STK-INT-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.stakeholders.application.dtos import RaciGenerationAssignment, RaciGenerationResult
from src.stakeholders.application.services.raci_generation_service import RaciGenerationService
from src.stakeholders.domain.models import InterestLevel, PowerLevel, RACIRole, Stakeholder


@pytest.mark.asyncio
async def test_i10_int_runtime_wires_canonical_service_through_i10_inference_gateway_red() -> None:
    """
    TS-I10-STK-INT-001:
    Canonical runtime path must wire RACI generation through I10 inference gateway.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    stakeholder_id = uuid4()
    wbs_item_id = uuid4()
    clause_id = uuid4()

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = (
        [
            Stakeholder(
                id=stakeholder_id,
                project_id=project_id,
                power_level=PowerLevel.HIGH,
                interest_level=InterestLevel.HIGH,
                approval_status="approved",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                name="Contractor Inc.",
                role="Contractor",
                organization="BuildCo",
                stakeholder_metadata={"type": "external"},
            )
        ],
        1,
    )
    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [
        SimpleNamespace(
            id=wbs_item_id,
            code="1.1.1",
            parent_code=None,
            name="Structural Works",
            description="Execute structural package",
            source_clause_id=clause_id,
        )
    ]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {
        clause_id: "The Contractor shall execute structural works."
    }
    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(assignments=[], warnings=[])
    stakeholder_repository = AsyncMock()
    i10_inference_service = AsyncMock()
    i10_inference_service.generate_raci_matrix.return_value = ([], [])

    service = RaciGenerationService(
        tenant_id=tenant_id,
        list_stakeholders_use_case=list_stakeholders_use_case,
        wbs_repository=wbs_repository,
        document_repository=document_repository,
        raci_generator=raci_generator,
        stakeholder_repository=stakeholder_repository,
        raci_inference_service=i10_inference_service,
    )

    await service.generate_and_persist(project_id)

    i10_inference_service.generate_raci_matrix.assert_awaited_once()


@pytest.mark.asyncio
async def test_i10_int_runtime_rejects_unresolved_stakeholder_ids_from_deprecated_identity_path_red() -> None:
    """
    TS-I10-STK-INT-001:
    Canonical runtime must reject unresolved/synthetic stakeholder IDs before persistence.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    known_stakeholder_id = uuid4()
    unknown_stakeholder_id = uuid4()
    wbs_item_id = uuid4()
    clause_id = uuid4()

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = (
        [
            Stakeholder(
                id=known_stakeholder_id,
                project_id=project_id,
                power_level=PowerLevel.MEDIUM,
                interest_level=InterestLevel.HIGH,
                approval_status="approved",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                name="Client Holdings",
                role="Client",
                organization="Owner Corp",
                stakeholder_metadata={"type": "owner"},
            )
        ],
        1,
    )
    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [
        SimpleNamespace(
            id=wbs_item_id,
            code="1.1.2",
            parent_code=None,
            name="Payment Certification",
            description="Review and approve payment certificate",
            source_clause_id=clause_id,
        )
    ]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {
        clause_id: "The Client shall approve payment certificates."
    }
    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(
        assignments=[
            RaciGenerationAssignment(
                wbs_item_id=wbs_item_id,
                stakeholder_id=unknown_stakeholder_id,
                role=RACIRole.ACCOUNTABLE,
                evidence_text="Unresolved identity candidate",
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
