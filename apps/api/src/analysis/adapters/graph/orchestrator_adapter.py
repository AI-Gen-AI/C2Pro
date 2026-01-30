from __future__ import annotations

from typing import Any

from src.analysis.adapters.graph.workflow import run_orchestration
from src.analysis.ports.orchestrator import AnalysisOrchestrator


class WorkflowOrchestrator(AnalysisOrchestrator):
    async def run(self, initial_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
        return await run_orchestration(initial_state, thread_id=thread_id)
