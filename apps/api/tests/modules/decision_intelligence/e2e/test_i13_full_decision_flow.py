"""TS-I13-E2E-001: End-to-end decision intelligence flow gating and finalization."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.modules.decision_intelligence.application.ports import DecisionOrchestrationService
from src.modules.decision_intelligence.domain.entities import FinalDecisionPackage


class MockIngestionService:
    async def ingest_document(self, doc_bytes: bytes) -> dict[str, Any]:
        return {
            "doc_id": uuid4(),
            "version_id": uuid4(),
            "chunks": [{"id": uuid4(), "content": "mocked chunk"}],
        }


class MockExtractionService:
    async def extract_clauses(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "clause_id": uuid4(),
                "text": "mocked clause",
                "confidence": 0.9,
                "metadata": {"citations": ["c1"]},
            }
        ]


class MockRetrievalService:
    async def retrieve(self, query: str) -> list[dict[str, Any]]:
        return [{"text": "evidence link 1", "score": 0.9}]


class MockCoherenceScoringService:
    async def aggregate_coherence_score(
        self, alerts: list[dict[str, Any]], tenant_id: UUID, project_id: UUID
    ) -> dict[str, Any]:
        return {"score": 0.75, "severity": "Medium", "explanation": {}, "metadata": {}}


class MockHumanInTheLoopService:
    async def route_for_review(
        self, item_id: UUID, item_type: str, confidence: float, impact_level: str, item_data: dict[str, Any]
    ) -> str:
        if confidence < 0.5:
            return "PENDING_REVIEW_REQUIRED"
        return "APPROVED"

    async def approve_item(self, item_id: UUID, reviewer_id: UUID, reviewer_name: str) -> dict[str, Any]:
        return {
            "item_id": item_id,
            "current_status": "APPROVED",
            "approved_by": reviewer_name,
            "approved_at": datetime.now().isoformat(),
        }


class MockLangSmithAdapter:
    async def start_run(self, *args: Any, **kwargs: Any) -> Any:
        return MagicMock(id=uuid4())

    async def end_run(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def log_event(self, *args: Any, **kwargs: Any) -> None:
        return None


@pytest.fixture
def mock_full_stack_services() -> dict[str, Any]:
    """Provides mocked services simulating the full AI core stack."""
    return {
        "ingestion_service": AsyncMock(spec=MockIngestionService),
        "extraction_service": AsyncMock(spec=MockExtractionService),
        "retrieval_service": AsyncMock(spec=MockRetrievalService),
        "coherence_scoring_service": AsyncMock(spec=MockCoherenceScoringService),
        "hitl_service": AsyncMock(spec=MockHumanInTheLoopService),
        "langsmith_adapter": AsyncMock(spec=MockLangSmithAdapter),
    }


@pytest.fixture
def decision_orchestration_service(mock_full_stack_services: dict[str, Any]) -> DecisionOrchestrationService:
    return DecisionOrchestrationService(
        ingestion_service=mock_full_stack_services["ingestion_service"],
        extraction_service=mock_full_stack_services["extraction_service"],
        retrieval_service=mock_full_stack_services["retrieval_service"],
        coherence_scoring_service=mock_full_stack_services["coherence_scoring_service"],
        hitl_service=mock_full_stack_services["hitl_service"],
        langsmith_adapter=mock_full_stack_services["langsmith_adapter"],
    )


@pytest.mark.asyncio
async def test_i13_e2e_full_flow_generates_score_and_risks_with_evidence(
    decision_orchestration_service: DecisionOrchestrationService, mock_full_stack_services: dict[str, Any]
) -> None:
    mock_doc_bytes = b"mock pdf content"
    tenant_id = uuid4()
    project_id = uuid4()

    final_package = await decision_orchestration_service.execute_full_decision_flow(
        document_bytes=mock_doc_bytes, tenant_id=tenant_id, project_id=project_id
    )

    assert isinstance(final_package, FinalDecisionPackage)
    assert final_package.coherence_score > 0
    assert len(final_package.risks) > 0
    assert len(final_package.evidence_links) > 0

    mock_full_stack_services["ingestion_service"].ingest_document.assert_called_once()
    mock_full_stack_services["extraction_service"].extract_clauses.assert_called_once()
    mock_full_stack_services["coherence_scoring_service"].aggregate_coherence_score.assert_called_once()


@pytest.mark.asyncio
async def test_i13_e2e_low_confidence_output_blocked_from_finalization(
    decision_orchestration_service: DecisionOrchestrationService, mock_full_stack_services: dict[str, Any]
) -> None:
    mock_doc_bytes = b"mock low confidence doc"
    tenant_id = uuid4()
    project_id = uuid4()

    mock_full_stack_services["coherence_scoring_service"].aggregate_coherence_score.return_value = {
        "score": 0.1,
        "severity": "Critical",
        "explanation": {},
        "metadata": {},
    }
    mock_full_stack_services["hitl_service"].route_for_review.return_value = "PENDING_REVIEW_REQUIRED"

    with pytest.raises(ValueError, match="Finalization blocked: Item requires review."):
        await decision_orchestration_service.execute_full_decision_flow(
            document_bytes=mock_doc_bytes, tenant_id=tenant_id, project_id=project_id
        )


@pytest.mark.asyncio
async def test_i13_e2e_missing_citations_prevents_finalization(
    decision_orchestration_service: DecisionOrchestrationService, mock_full_stack_services: dict[str, Any]
) -> None:
    mock_doc_bytes = b"mock doc with no citations"
    tenant_id = uuid4()
    project_id = uuid4()

    mock_full_stack_services["extraction_service"].extract_clauses.return_value = [
        {"clause_id": uuid4(), "text": "clause without citation", "confidence": 0.9, "metadata": {"citations": []}}
    ]

    with pytest.raises(ValueError, match="Finalization blocked: Missing required citations."):
        await decision_orchestration_service.execute_full_decision_flow(
            document_bytes=mock_doc_bytes, tenant_id=tenant_id, project_id=project_id
        )


@pytest.mark.asyncio
async def test_i13_e2e_reviewer_approval_unlocks_final_decision_package(
    decision_orchestration_service: DecisionOrchestrationService, mock_full_stack_services: dict[str, Any]
) -> None:
    mock_doc_bytes = b"mock doc needs approval"
    tenant_id = uuid4()
    project_id = uuid4()
    reviewer_id = uuid4()
    reviewer_name = "Approved Reviewer"

    mock_full_stack_services["coherence_scoring_service"].aggregate_coherence_score.return_value = {
        "score": 0.75,
        "severity": "Medium",
        "explanation": {},
        "metadata": {},
    }
    mock_full_stack_services["hitl_service"].approve_item.return_value = {
        "item_id": uuid4(),
        "current_status": "APPROVED",
        "approved_by": reviewer_name,
        "approved_at": datetime.now().isoformat(),
    }

    final_package = await decision_orchestration_service.execute_full_decision_flow(
        document_bytes=mock_doc_bytes,
        tenant_id=tenant_id,
        project_id=project_id,
        review_decision={
            "item_id": uuid4(),
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer_name,
            "action": "approve",
        },
    )

    assert isinstance(final_package, FinalDecisionPackage)
    assert final_package.approved_by == reviewer_name
    assert final_package.approved_at is not None


@pytest.mark.asyncio
async def test_i13_e2e_final_decision_pack_requires_mandatory_sign_off(
    decision_orchestration_service: DecisionOrchestrationService, mock_full_stack_services: dict[str, Any]
) -> None:
    mock_doc_bytes = b"mock doc needs signoff"
    tenant_id = uuid4()
    project_id = uuid4()

    mock_full_stack_services["coherence_scoring_service"].aggregate_coherence_score.return_value = {
        "score": 0.95,
        "severity": "Low",
        "explanation": {},
        "metadata": {"requires_reviewer_acknowledgment": True},
    }

    with pytest.raises(ValueError, match="Finalization blocked: Mandatory sign-off required."):
        await decision_orchestration_service.execute_full_decision_flow(
            document_bytes=mock_doc_bytes,
            tenant_id=tenant_id,
            project_id=project_id,
            review_decision={
                "item_id": uuid4(),
                "reviewer_id": uuid4(),
                "reviewer_name": "Signer Name",
                "action": "approve",
            },
        )
