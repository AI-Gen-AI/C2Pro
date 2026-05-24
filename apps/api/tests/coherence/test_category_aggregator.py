"""
Tests for the per-category aggregator (ADR-009 §6, §10, §13).

Refers to Suite ID: TS-UA-COH-V2-CATAGG-001.
"""
from __future__ import annotations

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
)
from src.coherence.domain.category_state_machine import CategoryStateMachine
from src.coherence.services.v2.category_aggregator import CategoryAggregator
from src.coherence.services.v2.conflict_service import ConflictReport
from src.coherence.services.v2.evidence_service import EvidenceBundle


def _bundle(count: int = 3, coverage: float = 0.9, tri: float = 0.85,
            freshness: float = 0.95) -> EvidenceBundle:
    return EvidenceBundle(
        count=count,
        evidence_coverage=coverage,
        evidence_freshness=freshness,
        avg_technical_reliability=tri,
        missing_required=[],
        references=[f"doc-{i}" for i in range(count)],
    )


def _no_conflict() -> ConflictReport:
    return ConflictReport(
        severity="none", hard_conflict=False, conflict_set=[], evidence_certainty=1.0
    )


@pytest.fixture
def aggregator() -> CategoryAggregator:
    return CategoryAggregator(CategoryStateMachine())


@pytest.mark.unit
def test_insufficient_evidence_yields_null_score(aggregator: CategoryAggregator) -> None:
    cat: CategoryV2 = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(count=1),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=True,
    )
    assert cat.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert cat.coherence_score is None


@pytest.mark.unit
def test_pending_documents_when_no_evidence(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="SCOPE",
        evidence=_bundle(count=0, coverage=0.0, tri=0.0, freshness=0.0),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=True,
    )
    assert cat.status is CategoryStatus.PENDING_DOCUMENTS
    assert cat.coherence_score is None


@pytest.mark.unit
def test_not_applicable_carries_reason(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="QUALITY",
        evidence=_bundle(count=5),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=False,
        applicability_reason="No quality-bound deliverables in contract.",
    )
    assert cat.status is CategoryStatus.NOT_APPLICABLE
    assert cat.coherence_score is None
    assert cat.applicability_reason == "No quality-bound deliverables in contract."


@pytest.mark.unit
@pytest.mark.parametrize(
    "severity,certainty,base,expected",
    [
        ("low", 1.0, 80.0, 72.0),       # 80 * 0.9 * 1.0
        ("medium", 0.9, 80.0, 50.4),    # 80 * 0.7 * 0.9
        ("high", 1.0, 80.0, 32.0),      # 80 * 0.4 * 1.0
        ("critical", 1.0, 80.0, 8.0),   # 80 * 0.1 * 1.0
    ],
)
def test_adjusted_score_formula_for_conflicts(
    aggregator: CategoryAggregator,
    severity: str,
    certainty: float,
    base: float,
    expected: float,
) -> None:
    conflict = ConflictReport(
        severity=severity,
        hard_conflict=True,
        conflict_set=[{"clauses": ["a", "b"]}],
        evidence_certainty=certainty,
    )
    cat = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(),
        conflict=conflict,
        rule_signals=[("dummy_rule", base)],
        applicable=True,
    )
    assert cat.status is CategoryStatus.CONFLICTING_EVIDENCE
    assert cat.coherence_score == pytest.approx(expected, rel=1e-6)


@pytest.mark.unit
def test_score_explanation_records_multipliers(aggregator: CategoryAggregator) -> None:
    conflict = ConflictReport(
        severity="medium",
        hard_conflict=True,
        conflict_set=[{"clauses": ["a", "b"]}],
        evidence_certainty=0.8,
    )
    cat = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(),
        conflict=conflict,
        rule_signals=[("budget_overrun", 90.0)],
        applicable=True,
    )
    assert cat.score_explanation is not None
    steps = {step["step"] for step in cat.score_explanation.score_path}
    assert {"base", "severity_multiplier", "evidence_certainty"} <= steps


@pytest.mark.unit
def test_scored_branch_returns_value_in_range(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="LEGAL",
        evidence=_bundle(count=1),  # LEGAL threshold = 1
        conflict=_no_conflict(),
        rule_signals=[("legal_clean", 100.0)],
        applicable=True,
    )
    assert cat.status is CategoryStatus.SCORED
    assert cat.coherence_score is not None
    assert 0.0 <= cat.coherence_score <= 100.0


@pytest.mark.unit
def test_evidence_freshness_is_propagated(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="LEGAL",
        evidence=_bundle(count=1, freshness=0.42),
        conflict=_no_conflict(),
        rule_signals=[("ok", 100.0)],
        applicable=True,
    )
    assert cat.evidence_freshness == pytest.approx(0.42)
