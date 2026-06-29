"""
TS-COH-LG-V3-001: deterministic evaluator error handling regressions.

Unexpected evaluator defects must not be hidden as partial coherence scores.
"""

import pytest

import src.coherence.graph.nodes as nodes_module
from src.coherence.graph.nodes import deterministic_evaluate
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.models import Clause


class TestDeterministicEvaluateErrors:
    """Regression coverage for deterministic evaluator exception handling."""

    def test_unexpected_evaluator_exception_propagates(self, monkeypatch):
        """TS-COH-LG-V3-001: unexpected evaluator defects are not hidden."""

        class UnexpectedEvaluatorError(Exception):
            pass

        class DefectiveEvaluator:
            source = "deterministic"
            category = "BUDGET"
            rule_id = "DET-DEFECT"

            def applicability(self, clause):
                raise UnexpectedEvaluatorError("broken evaluator")

        state = CoherenceGraphState(
            project_id="test",
            clauses=[
                Clause(
                    id="BUD-001",
                    text="Project Budget: Approved $100,000. Current spent: $125,000.",
                    data={"planned": 100000, "current": 125000},
                )
            ],
            config=EvaluationConfig(low_budget_mode=True),
        )
        monkeypatch.setattr(nodes_module, "list_evaluators", lambda: [DefectiveEvaluator()])

        with pytest.raises(UnexpectedEvaluatorError):
            deterministic_evaluate(state)
