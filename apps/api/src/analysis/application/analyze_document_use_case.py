from __future__ import annotations

from typing import Any

from src.analysis.ports.orchestrator import AnalysisOrchestrator


class AnalyzeDocumentUseCase:
    def __init__(self, orchestrator: AnalysisOrchestrator) -> None:
        self.orchestrator = orchestrator

    async def execute(
        self,
        *,
        document_text: str,
        project_id: str,
        document_id: str | None,
        tenant_id: str | None,
    ) -> dict[str, Any]:
        initial_state = {
            "document_text": document_text,
            "project_id": project_id,
            "document_id": document_id or project_id,
            "doc_type": "",
            "tenant_id": tenant_id,
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
        return await self.orchestrator.run(initial_state, thread_id=project_id)
