"""TS-COH-BUD-RECON-001: deterministic budget reconciliation through coherence graph."""

from __future__ import annotations

from uuid import uuid4

from src.coherence.graph.graph import evaluate_coherence
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause


def test_budget_reconciliation_marks_budget_assessed_with_both_alerts(monkeypatch) -> None:
    """TS-COH-BUD-RECON-004: contract and declared totals assess BUDGET without LLM."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setattr("langchain_core.tracers.context._get_tracer_project", lambda: "test")
    project_id = uuid4()
    clauses = [
        Clause(
            id="bom-line-1",
            text="Total BOM line",
            data={
                "document_type": "budget",
                "source": "procurement_bom",
                "category": "BUDGET",
                "affected_categories": ["BUDGET"],
                "unit_price": 636_044_805.0,
                "quantity": 1.0,
                "line_total": 636_044_805.0,
                "total": 636_044_805.0,
            },
        ),
        Clause(
            id=f"budget-reconciliation-{project_id}",
            text="Project budget vs contract reconciliation",
            data={
                "document_type": "budget",
                "category": "BUDGET",
                "affected_categories": ["BUDGET"],
                "budget_items": [{"amount": 636_044_805.0, "name": "BOM total"}],
                "contract_total": 628_624_801.0,
                "stated_total": 654_144_805.0,
            },
        ),
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id=str(project_id),
        config=EvaluationConfig(low_budget_mode=True),
    )

    budget = next(item for item in result.category_breakdown if item.category == "financial")
    assert budget.state == "assessed_findings"
    assert any(alert.rule_id == "DET-BUD-SUM" for alert in result.alerts)
    assert any(alert.rule_id == "DET-BUD-INTERNAL" for alert in result.alerts)
    assert result.llm_cost_usd == 0.0
