"""
I10 - Stakeholder Resolution + RACI Inference (Application)
Test Suite ID: TS-I10-STKH-APP-001
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.stakeholders.application.ports import (
    RACIInferenceService,
    StakeholderRepository,
)
from src.modules.stakeholders.domain.entities import (
    PartyResolutionResult,
    RACIRole,
    Stakeholder,
)
from src.modules.stakeholders.domain.services import RACIValidator, StakeholderResolver


@pytest.fixture
def mock_stakeholder_repo() -> AsyncMock:
    repo = AsyncMock(spec=StakeholderRepository)
    repo.get_all_stakeholders.return_value = []
    repo.add_stakeholder.return_value = Stakeholder(
        id=uuid4(),
        name="Contractor",
        canonical_id=uuid4(),
        aliases={"Contractor"},
        confidence=0.9,
    )
    repo.update_stakeholder.return_value = repo.add_stakeholder.return_value
    return repo


@pytest.fixture
def mock_llm_generator() -> AsyncMock:
    llm = AsyncMock()
    llm.generate_structured_output.return_value = {
        "raci_activities": [
            {
                "activity_id": str(uuid4()),
                "description": "Review and approve payment certificate.",
                "responsibilities": [
                    {"stakeholder_name": "Contractor", "role": RACIRole.RESPONSIBLE.value},
                    {"stakeholder_name": "Client", "role": RACIRole.ACCOUNTABLE.value},
                ],
                "confidence": 0.93,
            }
        ],
        "ambiguous_mappings": [],
    }
    return llm


@pytest.fixture
def mock_resolver() -> MagicMock:
    resolver = MagicMock(spec=StakeholderResolver)
    resolver.resolve_entity.side_effect = [
        PartyResolutionResult(
            original_name="Contractor",
            resolved_stakeholder_id=uuid4(),
            canonical_id=uuid4(),
            ambiguity_flag=False,
            action="merged",
        ),
        PartyResolutionResult(
            original_name="Client",
            resolved_stakeholder_id=None,
            canonical_id=uuid4(),
            ambiguity_flag=True,
            action="new_with_canonical",
            warning_message="Potentially ambiguous with multiple client entities.",
        ),
    ]
    return resolver


@pytest.fixture
def mock_raci_validator() -> MagicMock:
    validator = MagicMock(spec=RACIValidator)
    validator.validate_activity_raci.return_value = []
    return validator


@pytest.fixture
def mock_contract_clauses() -> list[ExtractedClause]:
    doc_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    return [
        ExtractedClause(
            clause_id=uuid4(),
            document_id=doc_id,
            version_id=version_id,
            chunk_id=chunk_id,
            text="The Contractor shall submit payment certificate, and the Client shall approve it.",
            type="Payment Obligation",
            modality="Shall",
            due_date=date(2026, 10, 1),
            penalty_linkage=None,
            confidence=0.97,
            ambiguity_flag=False,
            actors=["Contractor", "Client"],
            metadata={},
        )
    ]


@pytest.mark.asyncio
async def test_i10_raci_inference_flags_ambiguous_stakeholder_mappings_for_review(
    mock_llm_generator: AsyncMock,
    mock_stakeholder_repo: AsyncMock,
    mock_resolver: MagicMock,
    mock_raci_validator: MagicMock,
    mock_contract_clauses: list[ExtractedClause],
) -> None:
    """Refers to I10.6: ambiguous mappings must be returned and tagged for PMO/legal validation."""
    service = RACIInferenceService(
        llm_generator=mock_llm_generator,
        stakeholder_repo=mock_stakeholder_repo,
        stakeholder_resolver=mock_resolver,
        raci_validator=mock_raci_validator,
    )

    raci_matrix, ambiguities = await service.generate_raci_matrix(
        contract_statements=mock_contract_clauses,
        tenant_id=uuid4(),
        project_id=uuid4(),
    )

    assert len(raci_matrix) > 0
    assert len(ambiguities) > 0
    assert any(a.get("entity_name") == "Client" for a in ambiguities)
    assert raci_matrix[0].metadata.get("requires_pmo_legal_validation") is True


@pytest.mark.asyncio
async def test_i10_raci_inference_enforces_raci_constraints_before_return(
    mock_llm_generator: AsyncMock,
    mock_stakeholder_repo: AsyncMock,
    mock_resolver: MagicMock,
    mock_raci_validator: MagicMock,
    mock_contract_clauses: list[ExtractedClause],
) -> None:
    """Refers to I10.2: invalid RACI assignments must fail contract generation."""
    mock_raci_validator.validate_activity_raci.return_value = [
        "Multiple Accountable roles are not allowed for one activity."
    ]
    service = RACIInferenceService(
        llm_generator=mock_llm_generator,
        stakeholder_repo=mock_stakeholder_repo,
        stakeholder_resolver=mock_resolver,
        raci_validator=mock_raci_validator,
    )

    with pytest.raises(ValueError, match="Multiple Accountable roles"):
        await service.generate_raci_matrix(
            contract_statements=mock_contract_clauses,
            tenant_id=uuid4(),
            project_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_i10_raci_inference_is_deterministic_for_same_inputs(
    mock_llm_generator: AsyncMock,
    mock_stakeholder_repo: AsyncMock,
    mock_resolver: MagicMock,
    mock_raci_validator: MagicMock,
    mock_contract_clauses: list[ExtractedClause],
) -> None:
    """Refers to I10.4: same clause set must produce stable RACI structure and ambiguity output."""
    tenant_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    project_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    service_a = RACIInferenceService(
        llm_generator=mock_llm_generator,
        stakeholder_repo=mock_stakeholder_repo,
        stakeholder_resolver=mock_resolver,
        raci_validator=mock_raci_validator,
    )
    service_b = RACIInferenceService(
        llm_generator=mock_llm_generator,
        stakeholder_repo=mock_stakeholder_repo,
        stakeholder_resolver=mock_resolver,
        raci_validator=mock_raci_validator,
    )

    matrix_a, ambiguities_a = await service_a.generate_raci_matrix(
        contract_statements=mock_contract_clauses,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    matrix_b, ambiguities_b = await service_b.generate_raci_matrix(
        contract_statements=mock_contract_clauses,
        tenant_id=tenant_id,
        project_id=project_id,
    )

    assert [item.description for item in matrix_a] == [item.description for item in matrix_b]
    assert ambiguities_a == ambiguities_b

