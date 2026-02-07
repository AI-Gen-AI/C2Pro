"""
Trigger analysis orchestration for a parsed document.

Refers to Suite ID: TS-INT-MOD-DOC-001.
"""

from __future__ import annotations

from src.analysis.ports.orchestrator import AnalysisOrchestrator
from src.documents.ports.document_repository import IDocumentRepository


class TriggerDocumentAnalysisUseCase:
    """Bridge documents to analysis orchestrator."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        orchestrator: AnalysisOrchestrator,
    ) -> None:
        self._document_repository = document_repository
        self._orchestrator = orchestrator

    async def execute(self, *, document_id) -> dict:
        document = await self._document_repository.get_by_id(document_id)
        if not document:
            raise ValueError("document not found")

        parsed_text = document.document_metadata.get("parsed_text") if document.document_metadata else None
        if not parsed_text:
            raise ValueError("parsed_text not available")

        tenant_id = await self._document_repository.get_project_tenant_id(document.project_id)
        if tenant_id is None:
            raise ValueError("tenant not found for project")

        initial_state = {
            "document_text": parsed_text,
            "project_id": str(document.project_id),
            "document_id": str(document.id),
            "doc_type": getattr(document.document_type, "value", "") if document.document_type else "",
            "tenant_id": str(tenant_id),
            "messages": [],
            "extracted_risks": [],
            "extracted_wbs": [],
            "confidence_score": 0.0,
            "critique_notes": "",
            "human_feedback": "",
            "retry_count": 0,
            "human_approval_required": False,
            "analysis_id": None,
        }

        return await self._orchestrator.run(initial_state, thread_id=str(document.project_id))
