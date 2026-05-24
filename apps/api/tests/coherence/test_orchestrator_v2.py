"""
End-to-end tests for the v2 orchestrator (ADR-009 §6).

Refers to Suite ID: TS-UA-COH-V2-ORCH-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CoherenceV2Payload,
)
from src.coherence.services.v2.category_aggregator import CategoryAggregator
from src.coherence.services.v2.conflict_service import ConflictReport, ConflictService
from src.coherence.services.v2.evidence_service import EvidenceBundle, EvidenceService
from src.coherence.services.v2.aggregator_v2 import GlobalAggregatorV2
from src.coherence.services.v2.orchestrator import (
    CoherenceV2Orchestrator,
    ProjectEvidenceInputs,
)
from src.coherence.domain.category_state_machine import CategoryStateMachine


class _StubEvidenceService(EvidenceService):
    def __init__(self, by_category: dict[str, EvidenceBundle]) -> None:
        self._by_category = by_category

    def collect(self, category: str, project_docs):  # type: ignore[override]
        return self._by_category.get(
            category,
            EvidenceBundle(0, 0.0, 0.0, 0.0, [], []),
        )


class _StubConflictService(ConflictService):
    def __init__(self, by_category: dict[str, ConflictReport] | None = None) -> None:
        self._by_category = by_category or {}

    def detect(self, category, evidence, rule_signals):  # type: ignore[override]
        return self._by_category.get(
            category,
            ConflictReport("none", False, [], 1.0),
        )


def _make_orchestrator(evidence_map, conflict_map=None) -> CoherenceV2Orchestrator:
    return CoherenceV2Orchestrator(
        evidence=_StubEvidenceService(evidence_map),
        conflict=_StubConflictService(conflict_map),
        cat_agg=CategoryAggregator(CategoryStateMachine()),
        global_agg=GlobalAggregatorV2(),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_project_yields_pending_documents() -> None:
    orch = _make_orchestrator({})
    payload: CoherenceV2Payload = await orch.run(
        project_id=uuid4(),
        evidence_inputs=ProjectEvidenceInputs(project_docs=[], project_context={}),
    )
    assert {c.category for c in payload.categories} == {
        "SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"
    }
    assert all(c.status is CategoryStatus.PENDING_DOCUMENTS for c in payload.categories)
    assert payload.global_.coherence_score is None
    assert payload.global_.status == "pending_documents"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_full_evidence_yields_scored_categories() -> None:
    full_bundle = EvidenceBundle(
        count=5, evidence_coverage=1.0, evidence_freshness=1.0,
        avg_technical_reliability=0.9, missing_required=[],
        references=[f"doc-{i}" for i in range(5)],
    )
    evidence = {c: full_bundle for c in
                ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")}
    orch = _make_orchestrator(evidence)
    payload = await orch.run(
        project_id=uuid4(),
        evidence_inputs=ProjectEvidenceInputs(project_docs=[1, 2, 3], project_context={}),
    )
    assert all(c.status is CategoryStatus.SCORED for c in payload.categories)
    assert payload.global_.coherence_score is not None
    assert payload.global_.status == "scored"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_one_critical_conflict_depresses_score_but_not_null() -> None:
    full_bundle = EvidenceBundle(
        count=5, evidence_coverage=1.0, evidence_freshness=1.0,
        avg_technical_reliability=0.9, missing_required=[],
        references=[f"doc-{i}" for i in range(5)],
    )
    evidence = {c: full_bundle for c in
                ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")}
    conflicts = {
        "BUDGET": ConflictReport(
            severity="critical", hard_conflict=True,
            conflict_set=[{"reason": "test"}], evidence_certainty=1.0,
        )
    }
    orch = _make_orchestrator(evidence, conflicts)
    payload = await orch.run(
        project_id=uuid4(),
        evidence_inputs=ProjectEvidenceInputs(project_docs=[1], project_context={}),
    )
    budget = next(c for c in payload.categories if c.category == "BUDGET")
    assert budget.status is CategoryStatus.CONFLICTING_EVIDENCE
    assert budget.coherence_score is not None
    assert budget.coherence_score < 50  # critical conflict suppresses score
    assert payload.global_.coherence_score is not None  # still scoreable


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_emits_payload_with_locked_contract() -> None:
    orch = _make_orchestrator({})
    payload = await orch.run(
        project_id=uuid4(),
        evidence_inputs=ProjectEvidenceInputs(project_docs=[], project_context={}),
    )
    assert payload.version == "coherence-v2"
    assert payload.generated_at.tzinfo is not None  # ISO-8601 with TZ
    assert isinstance(payload.generated_at, datetime)
