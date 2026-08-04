"""Conflict candidate ledger contracts for TASK-COH-V2-CROSSDOC-SIGNAL-LEDGER.

Refers to Suite ID: TS-UA-COH-V2-CONFLICT-LEDGER-001.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.models import FindingSignal
from src.coherence.services.v2.aggregator_v2 import GlobalAggregatorV2
from src.coherence.services.v2.category_aggregator import CategoryAggregator
from src.coherence.services.v2.conflict_service import (
    ConflictCandidate,
    ConflictReport,
    ConflictService,
    build_conflict_candidates,
)
from src.coherence.services.v2.evidence_service import EvidenceBundle, EvidenceService
from src.coherence.services.v2.orchestrator import (
    CoherenceV2Orchestrator,
    ProjectEvidenceInputs,
)


def _budget_sum_signal() -> FindingSignal:
    return FindingSignal(
        rule_id="DET-BUD-SUM",
        clause_id="clause-budget-001",
        source="deterministic",
        impact_score=0.75,
        confidence=1.0,
        severity="high",
        category="BUDGET",
        evidence_summary="not carried into the conflict ledger",
        quote="not carried into the conflict ledger",
        raw_data={
            "items_sum": 125_000.0,
            "contract_total": 100_000.0,
            "deviation_pct": 25.0,
            "direction": "exceeds",
        },
    )


@pytest.mark.unit
def test_conflict_ledger_keeps_only_sanitized_cross_value_budget_provenance() -> None:
    """DET-BUD-SUM retains values/delta/clause provenance but not raw text or items."""
    candidates = build_conflict_candidates([_budget_sum_signal()])

    assert candidates == [
        ConflictCandidate(
            rule_id="DET-BUD-SUM",
            category="BUDGET",
            source_clause_id="clause-budget-001",
            compared_values={"items_sum": 125_000.0, "contract_total": 100_000.0},
            delta=25_000.0,
            direction="exceeds",
            deterministic_certainty=1.0,
        )
    ]


@pytest.mark.unit
def test_conflict_ledger_excludes_single_clause_risk_states() -> None:
    """An overrun remains a score signal, never a future hard-conflict candidate."""
    risk_signal = FindingSignal(
        rule_id="DET-BUD-OVERRUN",
        clause_id="clause-budget-002",
        source="deterministic",
        impact_score=0.75,
        confidence=1.0,
        severity="high",
        category="BUDGET",
        raw_data={"current": 125_000.0, "planned": 100_000.0},
    )

    assert build_conflict_candidates([risk_signal]) == []


class _CapturingConflictService(ConflictService):
    def __init__(self) -> None:
        self.candidates_by_category: dict[str, list[ConflictCandidate]] = {}

    def detect(  # type: ignore[override]
        self,
        category: str,
        evidence: EvidenceBundle,
        candidates: list[ConflictCandidate],
    ) -> ConflictReport:
        del evidence
        self.candidates_by_category[category] = candidates
        return ConflictReport("none", False, [], 1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_forwards_ledger_without_changing_category_score() -> None:
    """The candidate ledger reaches the stub conflict service; scoring stays tuple-based."""
    candidate = build_conflict_candidates([_budget_sum_signal()])[0]
    conflict = _CapturingConflictService()
    orchestrator = CoherenceV2Orchestrator(
        evidence=EvidenceService(),
        conflict=conflict,
        cat_agg=CategoryAggregator(),
        global_agg=GlobalAggregatorV2(),
    )
    payload = await orchestrator.run(
        project_id=uuid4(),
        evidence_inputs=ProjectEvidenceInputs(
            project_docs=[
                type("BudgetDocument", (), {"document_type": "budget", "id": index})()
                for index in range(3)
            ],
            project_context={},
            rule_signals_by_category={"BUDGET": [("DET-BUD-SUM", 25.0)]},
            conflict_candidates_by_category={"BUDGET": [candidate]},
        ),
    )

    budget = next(category for category in payload.categories if category.category == "BUDGET")
    assert conflict.candidates_by_category["BUDGET"] == [candidate]
    assert budget.coherence_score == 25.0
    assert budget.status.value == "scored"
