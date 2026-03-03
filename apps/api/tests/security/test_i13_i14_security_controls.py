"""
I13/I14 security controls for final output gating.

Test Suite ID: TS-SEC-S6-001
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.modules.decision_intelligence.application.ports import DecisionOrchestrationService
from src.modules.decision_intelligence.domain.exceptions import FinalizationBlockedError
from src.modules.governance.application.services import GovernanceOutputGuardService
from src.modules.governance.domain.entities import RiskLevel
from src.modules.governance.domain.exceptions import GovernancePolicyViolation


class _StubIngestion:
    async def ingest_document(self, doc_bytes: bytes) -> dict[str, Any]:
        return {"doc_id": uuid4(), "version_id": uuid4(), "chunks": [{"id": uuid4(), "content": "chunk"}]}


class _StubExtraction:
    async def extract_clauses(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"clause_id": uuid4(), "text": "clause", "confidence": 0.9, "metadata": {"citations": ["c1"]}}]


class _StubRetrieval:
    async def retrieve(self, query: str) -> list[dict[str, Any]]:
        return [{"text": "evidence", "score": 0.88}]


class _StubCoherenceScoring:
    async def aggregate_coherence_score(
        self, alerts: list[dict[str, Any]], tenant_id: UUID, project_id: UUID
    ) -> dict[str, Any]:
        return {"score": 0.78, "severity": "Medium", "explanation": {}, "metadata": {}}


class _StubHITL:
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
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }


def _make_service() -> DecisionOrchestrationService:
    return DecisionOrchestrationService(
        ingestion_service=_StubIngestion(),
        extraction_service=_StubExtraction(),
        retrieval_service=_StubRetrieval(),
        coherence_scoring_service=_StubCoherenceScoring(),
        hitl_service=_StubHITL(),
    )


@pytest.mark.asyncio
async def test_s6_i13_low_confidence_cannot_be_bypassed_with_inline_approval() -> None:
    service = _make_service()

    with pytest.raises(FinalizationBlockedError, match="Item requires review"):
        await service.execute_full_decision_flow(
            document_bytes=b"doc",
            tenant_id=uuid4(),
            project_id=uuid4(),
            force_profile="low_confidence",
            review_decision={
                "item_id": str(uuid4()),
                "reviewer_id": str(uuid4()),
                "reviewer_name": "Inline Reviewer",
                "action": "approve",
            },
        )


def test_s6_i14_override_cannot_bypass_missing_citations_even_with_sign_off() -> None:
    service = GovernanceOutputGuardService()

    with pytest.raises(GovernancePolicyViolation, match="missing_citations"):
        service.enforce(
            risk_level=RiskLevel.HIGH,
            has_citations=False,
            has_reviewer_sign_off=True,
            override_requested=True,
            output_payload={"message": "must block"},
        )


def test_s6_i14_high_risk_without_sign_off_is_always_blocked() -> None:
    service = GovernanceOutputGuardService()

    with pytest.raises(GovernancePolicyViolation, match="mandatory_sign_off_required"):
        service.enforce(
            risk_level=RiskLevel.HIGH,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=False,
            output_payload={"message": "must block"},
        )
