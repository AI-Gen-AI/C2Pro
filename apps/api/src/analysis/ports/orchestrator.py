"""
Analysis Orchestrator Port (Interface).
Part of TASK-BCK-022: Wire TriggerDocumentAnalysisUseCase to Celery ingestion completion.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AnalysisOrchestrator(ABC):
    """
    Port (interface) for analysis orchestration systems.

    Defines the contract that all orchestrator implementations must follow.
    This abstraction allows us to swap orchestration backends without
    changing the use case layer.
    """

    @abstractmethod
    async def run(self, initial_state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        """
        Run the analysis orchestration workflow.

        Args:
            initial_state: Initial state dictionary for the workflow
            thread_id: Unique identifier for this thread (used for checkpointing)

        Returns:
            Final state dictionary after workflow execution

        Raises:
            OrchestratorError: If orchestration fails
        """
        pass
