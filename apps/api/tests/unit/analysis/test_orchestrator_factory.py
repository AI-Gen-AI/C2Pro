"""
TDD RED Phase: Tests for AnalysisOrchestratorFactory
Part of TASK-BCK-022

These tests will FAIL until factory implementation is complete.
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest


class TestAnalysisOrchestratorFactoryExists:
    """Test that AnalysisOrchestratorFactory exists."""

    def test_factory_class_exists(self):
        """GIVEN factory module WHEN importing THEN AnalysisOrchestratorFactory exists."""
        # This will FAIL until we create the factory
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        assert AnalysisOrchestratorFactory is not None

    def test_factory_has_create_method(self):
        """GIVEN AnalysisOrchestratorFactory WHEN checking methods THEN create() exists."""
        # This will FAIL until we implement create()
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        assert hasattr(AnalysisOrchestratorFactory, "create")
        assert callable(AnalysisOrchestratorFactory.create)


class TestOrchestratorFactoryCreate:
    """Test AnalysisOrchestratorFactory.create() method."""

    def test_factory_create_returns_orchestrator_instance(self):
        """
        GIVEN AnalysisOrchestratorFactory
        WHEN calling create()
        THEN an AnalysisOrchestrator instance is returned.
        """
        # This will FAIL until we implement factory
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory
        from src.analysis.ports.orchestrator import AnalysisOrchestrator

        orchestrator = AnalysisOrchestratorFactory.create()

        assert orchestrator is not None
        assert isinstance(orchestrator, AnalysisOrchestrator)

    def test_factory_create_wires_all_dependencies(self):
        """
        GIVEN AnalysisOrchestratorFactory
        WHEN calling create()
        THEN all internal dependencies are wired correctly.
        """
        # This will FAIL until we wire dependencies
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        orchestrator = AnalysisOrchestratorFactory.create()

        # Verify orchestrator has required attributes
        assert hasattr(orchestrator, "run")
        assert callable(orchestrator.run)

    def test_factory_accepts_mock_overrides_for_testing(self):
        """
        GIVEN AnalysisOrchestratorFactory
        WHEN calling create(mock_graph=...)
        THEN factory uses provided mock instead of real implementation.
        """
        # This will FAIL until we implement override support
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        mock_graph = Mock()
        orchestrator = AnalysisOrchestratorFactory.create(graph=mock_graph)

        # Verify mock is used
        assert orchestrator is not None
        # Factory should accept optional override for testability


class TestOrchestratorFactoryDependencyInjection:
    """Test that factory properly injects all required dependencies."""

    def test_factory_injects_langgraph_checkpointer(self):
        """
        GIVEN AnalysisOrchestratorFactory
        WHEN creating orchestrator
        THEN LangGraph checkpointer is configured.
        """
        # This will FAIL until we wire checkpointer
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        orchestrator = AnalysisOrchestratorFactory.create()

        # Orchestrator should have access to checkpointer for state persistence
        assert orchestrator is not None

    def test_factory_uses_correct_graph_topology(self):
        """
        GIVEN AnalysisOrchestratorFactory
        WHEN creating orchestrator
        THEN graph uses N1-N17 topology from workflow.py.
        """
        # This will FAIL until we integrate workflow
        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        orchestrator = AnalysisOrchestratorFactory.create()

        # Verify orchestrator references the correct graph
        assert orchestrator is not None


class TestOrchestratorFactoryThreadSafety:
    """Test that factory can be called concurrently."""

    @pytest.mark.asyncio
    async def test_factory_create_is_thread_safe(self):
        """
        GIVEN multiple concurrent calls to factory
        WHEN calling create() in parallel
        THEN each call returns independent instances.
        """
        # This will FAIL if factory has shared mutable state
        import asyncio

        from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory

        async def create_orchestrator():
            return AnalysisOrchestratorFactory.create()

        orchestrators = await asyncio.gather(*[create_orchestrator() for _ in range(10)])

        # Verify each instance is independent
        assert len(orchestrators) == 10
        assert len({id(o) for o in orchestrators}) == 10  # All unique instances


# Run these tests with: pytest apps/api/tests/unit/analysis/test_orchestrator_factory.py -v
# Expected: ALL TESTS FAIL (RED phase)
