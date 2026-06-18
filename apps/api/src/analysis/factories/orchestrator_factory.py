"""
AnalysisOrchestratorFactory - Dependency Injection for Analysis Orchestration.
Part of TASK-BCK-022: Wire TriggerDocumentAnalysisUseCase to Celery ingestion completion.
"""
from __future__ import annotations

from typing import Any

from src.analysis.ports.orchestrator import AnalysisOrchestrator


class LangGraphOrchestrator(AnalysisOrchestrator):
    """
    LangGraph-based implementation of AnalysisOrchestrator.

    Wraps the existing LangGraph workflow (N1-N17 topology) into the
    AnalysisOrchestrator interface.
    """

    def __init__(self, graph_app: Any | None = None):
        """
        Initialize LangGraph orchestrator.

        Args:
            graph_app: Optional LangGraph app override for testing (default: uses real workflow)
        """
        self._graph_app = graph_app

    async def run(self, initial_state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        """
        Run LangGraph orchestration workflow.

        Args:
            initial_state: Initial state dictionary
            thread_id: Unique thread identifier for checkpointing

        Returns:
            Final state after workflow execution
        """
        # Lazy import to avoid circular dependencies
        from src.analysis.adapters.graph.workflow import run_orchestration

        if self._graph_app is not None:
            config = {
                "configurable": {"thread_id": thread_id},
                "run_name": f"test_{thread_id}",
                "tags": ["test"],
                "metadata": {"thread_id": thread_id},
            }
            result = await self._graph_app.ainvoke(initial_state, config)
        else:
            result = await run_orchestration(initial_state, thread_id)

        from src.analysis.application.document_artifact_completion import (
            persist_artifact_and_enqueue_project_graph,
        )

        await persist_artifact_and_enqueue_project_graph(result)
        return result


class AnalysisOrchestratorFactory:
    """
    Factory for creating AnalysisOrchestrator instances.

    Provides centralized dependency injection for orchestrator construction,
    making it easy to:
    - Swap orchestration backends
    - Override dependencies for testing
    - Ensure consistent configuration
    """

    @classmethod
    def create(cls, *, graph: Any | None = None) -> AnalysisOrchestrator:
        """
        Create an AnalysisOrchestrator instance.

        Args:
            graph: Optional graph override for testing (default: uses real LangGraph workflow)

        Returns:
            Configured AnalysisOrchestrator instance

        Example (Production):
            >>> orchestrator = AnalysisOrchestratorFactory.create()
            >>> result = await orchestrator.run(initial_state, thread_id="123")

        Example (Testing):
            >>> mock_graph = Mock()
            >>> mock_graph.ainvoke = AsyncMock(return_value={"status": "completed"})
            >>> orchestrator = AnalysisOrchestratorFactory.create(graph=mock_graph)
            >>> result = await orchestrator.run({}, thread_id="test")
        """
        return LangGraphOrchestrator(graph_app=graph)
