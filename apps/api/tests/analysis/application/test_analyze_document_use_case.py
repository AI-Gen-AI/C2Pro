"""
TS-UA-ANA-UC-002 - Fresh analysis orchestration thread identity tests.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.analysis.application.analyze_document_use_case import AnalyzeDocumentUseCase


class _CapturingOrchestrator:
    def __init__(self) -> None:
        self.thread_ids: list[str] = []

    async def run(self, initial_state: dict[str, object], thread_id: str) -> dict[str, object]:
        self.thread_ids.append(thread_id)
        return initial_state


@pytest.mark.asyncio
async def test_fresh_analysis_uses_unique_thread_id_per_request() -> None:
    """TS-UA-ANA-UC-002 - Fresh analyses for one project must not reuse checkpoint threads."""
    orchestrator = _CapturingOrchestrator()
    use_case = AnalyzeDocumentUseCase(orchestrator)

    await use_case.execute(
        document_text="contract",
        project_id="project-1",
        document_id="document-1",
        tenant_id="tenant-1",
    )
    await use_case.execute(
        document_text="contract",
        project_id="project-1",
        document_id="document-1",
        tenant_id="tenant-1",
    )

    assert len(orchestrator.thread_ids) == 2
    assert orchestrator.thread_ids[0] != orchestrator.thread_ids[1]
    for thread_id in orchestrator.thread_ids:
        UUID(thread_id)
