"""#860 -- the primary v1 path never reports BUDGET clean without a budget-line source.

TS-UA-860-V1-BUDGET-COVERAGE-001. The declared-total clause from the budget clause
builder is routed to BUDGET by ``document_type="budget"``; routing alone must not
mark BUDGET assessed (which reports ``assessed_clean`` and puts its baseline into
the headline score) while no authoritative structured budget-line set exists.
The withholding is generic: any clause may declare categories it cannot assess
(``assessment_unavailable``); budget findings stay visible as alerts.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.domain.budget_line_availability import STRUCTURED_BUDGET_SOURCE_UNAVAILABLE
from src.coherence.graph.graph import evaluate_coherence, evaluate_coherence_async
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause, FindingSignal


def _declared_total_clause(**extra: object) -> Clause:
    data: dict[str, object] = {
        "document_type": "budget",
        "source": "budget_document_metadata",
        "category": "BUDGET",
        "affected_categories": ["BUDGET"],
        "stated_total": 310.0,
        "budget_line_items": "unavailable",
        "budget_line_items_reason": STRUCTURED_BUDGET_SOURCE_UNAVAILABLE,
        "assessment_unavailable": {"BUDGET": STRUCTURED_BUDGET_SOURCE_UNAVAILABLE},
    }
    data.update(extra)
    return Clause(
        id=f"budget-reconciliation-{uuid4()}",
        text="Project budget vs contract reconciliation",
        data=data,
    )


def _legal_clause() -> Clause:
    return Clause(
        id="legal-1",
        text="The Contractor shall indemnify the Employer against all third-party claims.",
        data={"document_type": "contract", "category": "LEGAL"},
    )


def _financial(result):  # type: ignore[no-untyped-def]
    return next(item for item in result.category_breakdown if item.category == "financial")


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setattr("langchain_core.tracers.context._get_tracer_project", lambda: "test")


def test_declared_total_alone_does_not_make_v1_budget_assessed_clean() -> None:
    result = evaluate_coherence(
        clauses=[_declared_total_clause(), _legal_clause()],
        project_id="p",
        config=EvaluationConfig(low_budget_mode=True),
    )

    financial = _financial(result)
    assert financial.state == "unassessed"
    assert financial.score is None
    assert financial.baseline_estimated is False


def test_budget_findings_stay_visible_while_budget_is_unassessed() -> None:
    clause = _declared_total_clause()
    retention = FindingSignal(
        rule_id="DET-BUD-RETENTION",
        clause_id="contract-retention-1",
        impact_score=0.4,
        confidence=1.0,
        severity="medium",
        category="BUDGET",
        evidence_summary="Retention above the contractual cap.",
    )

    import asyncio

    result = asyncio.run(
        evaluate_coherence_async(
            clauses=[clause, _legal_clause()],
            project_id="p",
            config=EvaluationConfig(low_budget_mode=True),
            seed_signals=[retention],
            seed_coverage={"BUDGET": True},
        )
    )

    financial = _financial(result)
    assert financial.state == "unassessed"
    assert financial.score is None
    assert financial.alert_count == 1
    assert any(alert.rule_id == "DET-BUD-RETENTION" for alert in result.alerts)


def test_withholding_is_driven_by_the_generic_marker_not_by_document_type() -> None:
    """Without the marker, a budget-typed clause keeps its routed coverage."""
    clause = _declared_total_clause()
    del clause.data["assessment_unavailable"]

    result = evaluate_coherence(
        clauses=[clause, _legal_clause()],
        project_id="p",
        config=EvaluationConfig(low_budget_mode=True),
    )

    assert _financial(result).state != "unassessed"
