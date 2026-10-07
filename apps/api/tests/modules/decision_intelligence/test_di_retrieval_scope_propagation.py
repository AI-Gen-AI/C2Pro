"""P0 security: the orchestration scopes retrieval to the authenticated tenant and request project."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.modules.decision_intelligence.application.ports import DecisionOrchestrationService


class _Retrieval:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def retrieve(self, query: str, *, tenant_id: UUID | None, project_id: UUID | None) -> list[dict[str, Any]]:
        self.calls.append({"query": query, "tenant_id": tenant_id, "project_id": project_id})
        return [{"text": "own evidence", "score": 0.9}]


class _Ingestion:
    async def ingest_document(self, doc_bytes: bytes) -> dict[str, Any]:
        return {"chunks": []}


class _Extraction:
    async def extract_clauses(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return []


class _Scoring:
    async def aggregate_coherence_score(self, alerts: list[dict[str, Any]], tenant_id: UUID, project_id: UUID) -> dict[str, Any]:
        return {"score": 0.9, "severity": "Low", "explanation": {}, "metadata": {}}


class _HITL:
    async def route_for_review(self, **_: Any) -> str:
        return "AUTO_APPROVED"

    async def approve_item(self, **_: Any) -> dict[str, Any]:
        return {}


@pytest.mark.asyncio
async def test_retrieval_is_called_with_the_callers_tenant_and_project() -> None:
    retrieval = _Retrieval()
    service = DecisionOrchestrationService(
        ingestion_service=_Ingestion(), extraction_service=_Extraction(), retrieval_service=retrieval,
        coherence_scoring_service=_Scoring(), hitl_service=_HITL(),
    )
    tenant_id, project_id = uuid4(), uuid4()
    package = await service.execute_full_decision_flow(document_bytes=b"x", tenant_id=tenant_id, project_id=project_id)

    assert retrieval.calls == [{"query": "decision-intelligence", "tenant_id": tenant_id, "project_id": project_id}]
    assert package.evidence_links == ["own evidence"]
