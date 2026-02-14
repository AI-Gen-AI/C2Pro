"""
Security tests for graph/coherence controls.
Test Suite ID: TS-SEC-GRAPH-COH-001
"""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.graph.application.ports import GraphBuilderService, GraphRepository
from src.modules.coherence.application.ports import CoherenceEngineService
from src.modules.coherence.domain.entities import CoherenceAlert, RuleInput
from src.modules.coherence.domain.rules import (
    ScheduleMismatchRule,
    BudgetMismatchRule,
    ScopeProcurementMismatchRule,
)


@pytest.fixture
def extracted_clause() -> ExtractedClause:
    return ExtractedClause(
        clause_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        chunk_id=uuid4(),
        text="The Contractor shall deliver goods by 2024-12-31.",
        type="Delivery Obligation",
        modality="Shall",
        due_date=date(2024, 12, 31),
        penalty_linkage="Late delivery penalty applies.",
        confidence=0.95,
        ambiguity_flag=False,
        actors=["Contractor"],
        metadata={},
    )


@pytest.mark.asyncio
async def test_i5_referential_validation_cannot_be_bypassed_before_edge_persistence(
    extracted_clause: ExtractedClause,
) -> None:
    """TS-SEC-GRAPH-COH-001 - Missing target node must block edge persistence path."""
    repo = AsyncMock(spec=GraphRepository)
    repo.add_node.return_value = extracted_clause.clause_id
    repo.get_node.return_value = None
    repo.add_edge.return_value = uuid4()  # Should never be called on missing target

    service = GraphBuilderService(graph_repository=repo)

    with pytest.raises(ValueError, match="Source or target node not found for edge."):
        await service.build_from_extracted_clauses([extracted_clause])

    repo.add_edge.assert_not_called()


def test_i6_rules_are_scoring_agnostic_and_return_normalized_alerts() -> None:
    """TS-SEC-GRAPH-COH-001 - Rule layer must produce alerts without scoring coupling."""
    rule_input = RuleInput(
        doc_id=uuid4(),
        schedule_data={"project_end": date(2024, 12, 31)},
        actual_dates={"project_end": date(2025, 1, 15)},
        budget_data={"allocated": 100000},
        actual_costs={"actual_spend": 115000},
        scope_data={"required_items": ["Material A", "Service B"]},
        procurement_items={"items_procured": ["Material A"]},
    )

    alerts = [
        ScheduleMismatchRule().evaluate(rule_input),
        BudgetMismatchRule().evaluate(rule_input),
        ScopeProcurementMismatchRule().evaluate(rule_input),
    ]
    produced = [a for a in alerts if a is not None]

    assert len(produced) == 3
    for alert in produced:
        assert isinstance(alert, CoherenceAlert)
        assert "score" not in alert.metadata
        assert "weight" not in alert.metadata
        assert "coherence_score" not in alert.metadata


class _StaticRule:
    def __init__(self, name: str, severity: str) -> None:
        self.name = name
        self._severity = severity

    def evaluate(self, rule_input: RuleInput) -> CoherenceAlert:
        return CoherenceAlert(
            type=f"{self.name} Alert",
            severity=self._severity,  # type: ignore[arg-type]
            message=f"Alert from {self.name}",
            evidence={"triggered": True},
            triggered_by_rule=self.name,
            doc_id=rule_input.doc_id,
        )


@pytest.mark.asyncio
async def test_i6_high_and_critical_alerts_require_human_review_flag() -> None:
    """TS-SEC-GRAPH-COH-001 - High/Critical coherence alerts must always be flagged for review."""
    engine = CoherenceEngineService(
        rules=[_StaticRule("HighRule", "High"), _StaticRule("CriticalRule", "Critical")]
    )
    rule_input = RuleInput(
        doc_id=uuid4(),
        schedule_data={"project_end": date(2024, 12, 31)},
        actual_dates={"project_end": date(2025, 1, 10)},
    )

    alerts = await engine.run_coherence_checks(rule_input)

    assert len(alerts) == 2
    for alert in alerts:
        assert alert.metadata.get("requires_human_review") is True
        assert alert.metadata.get("review_reason") in {
            "High Coherence Conflict",
            "Critical Coherence Conflict",
        }
