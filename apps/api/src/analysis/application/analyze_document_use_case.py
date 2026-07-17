from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.analysis.ports.orchestrator import AnalysisOrchestrator
from src.core.json_types import JsonDict


class AnalyzeDocumentUseCase:
    """TS-UA-ANA-UC-002 - Orchestrate a fresh document analysis run."""
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
        thread_id = str(uuid4())
        initial_state: JsonDict = {
            "document_text": document_text,
            "project_id": project_id,
            "document_id": document_id or project_id,
            "doc_type": "",
            "tenant_id": tenant_id,
            "thread_id": thread_id,
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
        return await self.orchestrator.run(initial_state, thread_id=thread_id)
