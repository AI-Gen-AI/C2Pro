"""
I10 - Deterministic Resolution Contract (Application, RED)
Test Suite ID: TS-I10-STK-APP-002
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.stakeholders.application.dtos import RaciGenerationAssignment, RaciGenerationResult
from src.stakeholders.application.services.raci_generation_service import RaciGenerationService
from src.stakeholders.domain.models import InterestLevel, PowerLevel, RACIRole, Stakeholder
from src.modules.stakeholders.domain.entities import Stakeholder as ResolverStakeholder
from src.modules.stakeholders.domain.services import StakeholderResolver


class _RealResolverBackedInferenceGateway:
    """Uses the real I10 resolver to produce ambiguity output without mocks."""

    def __init__(self) -> None:
        self._resolver = StakeholderResolver()

    async def generate_raci_matrix(
        self,
        contract_statements: list[dict[str, str]],
        tenant_id: UUID,
        project_id: UUID | None = None,
    ) -> tuple[list[dict], list[dict[str, str]]]:
        _ = (contract_statements, tenant_id, project_id)
        existing = [
            ResolverStakeholder(
                id=uuid4(),
                name="Client Holdings LLC",
                canonical_id=uuid4(),
                aliases={"Client Holdings"},
                confidence=0.90,
            ),
            ResolverStakeholder(
                id=uuid4(),
                name="Client Holdings Group",
                canonical_id=uuid4(),
                aliases={"Client Holdings"},
                confidence=0.88,
            ),
        ]
        resolution = self._resolver.resolve_entity("Client Holdings", existing)
        if resolution.ambiguity_flag:
            return [], [{"entity_name": "Client Holdings"}]
        return [], []


def _stakeholder(project_id: UUID, stakeholder_id: UUID) -> Stakeholder:
    now = datetime.utcnow()
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


@pytest.mark.asyncio
async def test_i10_app_emits_deterministic_hitl_validation_error_from_real_resolver_red() -> None:
    """
    TS-I10-STK-APP-002:
    application flow must fail with HITL validation error when real resolver reports ambiguity.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    stakeholder_id = uuid4()
    wbs_item_id = uuid4()
    clause_id = uuid4()

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = ([_stakeholder(project_id, stakeholder_id)], 1)

    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [
        SimpleNamespace(
            id=wbs_item_id,
            code="1.1.1",
            parent_code=None,
            name="Payment certificate",
            description="Approve payment certificate",
            source_clause_id=clause_id,
        )
    ]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {
        clause_id: "The Client shall approve payment certificates.",
    }

    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(
        assignments=[
            RaciGenerationAssignment(
                wbs_item_id=wbs_item_id,
                stakeholder_id=stakeholder_id,
                role=RACIRole.ACCOUNTABLE,
                evidence_text="Payment clause evidence",
            )
        ],
        warnings=[],
    )

    stakeholder_repository = AsyncMock()
    stakeholder_repository.list_raci_assignments.return_value = []
    inference_gateway = _RealResolverBackedInferenceGateway()

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


@pytest.mark.asyncio
async def test_i10_app_hitl_validation_error_is_deterministic_for_same_input_with_real_resolver_red() -> None:
    """
    TS-I10-STK-APP-002:
    same normalized inputs must produce stable HITL validation error using a real resolver path.
    """
    tenant_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    project_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    stakeholder_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    wbs_item_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    clause_id = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

    list_stakeholders_use_case = AsyncMock()
    list_stakeholders_use_case.execute.return_value = ([_stakeholder(project_id, stakeholder_id)], 1)
    wbs_repository = AsyncMock()
    wbs_repository.get_by_project.return_value = [
        SimpleNamespace(
            id=wbs_item_id,
            code="1.1.1",
            parent_code=None,
            name="Payment certificate",
            description="Approve payment certificate",
            source_clause_id=clause_id,
        )
    ]
    document_repository = AsyncMock()
    document_repository.get_clause_text_map.return_value = {
        clause_id: "The Client shall approve payment certificates.",
    }
    raci_generator = AsyncMock()
    raci_generator.generate_assignments.return_value = RaciGenerationResult(
        assignments=[
            RaciGenerationAssignment(
                wbs_item_id=wbs_item_id,
                stakeholder_id=stakeholder_id,
                role=RACIRole.ACCOUNTABLE,
                evidence_text="Payment clause evidence",
            )
        ],
        warnings=[],
    )
    stakeholder_repository = AsyncMock()
    stakeholder_repository.list_raci_assignments.return_value = []

    service_a = RaciGenerationService(
        tenant_id=tenant_id,
        list_stakeholders_use_case=list_stakeholders_use_case,
        wbs_repository=wbs_repository,
        document_repository=document_repository,
        raci_generator=raci_generator,
        stakeholder_repository=stakeholder_repository,
        raci_inference_service=_RealResolverBackedInferenceGateway(),
    )
    service_b = RaciGenerationService(
        tenant_id=tenant_id,
        list_stakeholders_use_case=list_stakeholders_use_case,
        wbs_repository=wbs_repository,
        document_repository=document_repository,
        raci_generator=raci_generator,
        stakeholder_repository=stakeholder_repository,
        raci_inference_service=_RealResolverBackedInferenceGateway(),
    )

    with pytest.raises(ValueError, match="requires PMO/legal validation"):
        await service_a.generate_and_persist(project_id)
    with pytest.raises(ValueError, match="requires PMO/legal validation"):
        await service_b.generate_and_persist(project_id)
