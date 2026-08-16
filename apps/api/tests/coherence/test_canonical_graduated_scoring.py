"""
Canonical graduated-scoring invariants (ADR-009 — 2026-08-16 GOVERNING amendment).

These lock the product decision that a critical/hard conflict must be *graduated,
monotonic, and calibratable* — NOT collapsed to zero, and with detection-certainty
scaling the PENALTY (higher certainty => stronger penalty => lower score), correcting
the inverted v2 `base × severity × certainty`.

Scope of THIS suite: the shadow v2 per-category path (`CategoryAggregator`), which is
the divergent scorer the amendment §D/§F calls out. Exact band floors / ceilings and
the HITL score-relaxation rule are pinned in a follow-up once the calibrated numbers
land; this suite asserts only the *direction/shape* invariants that the amendment
ratifies and that cannot change.

Refers to Suite ID: TS-UA-COH-CANON-001.
"""
from __future__ import annotations

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus, CategoryV2
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


def _conflict(severity: str = "critical", certainty: float = 1.0) -> ConflictReport:
    return ConflictReport(
        severity=severity,  # type: ignore[arg-type]
        hard_conflict=True,
        conflict_set=[
            {
                "rule_id": "DET-BUD-SUM",
                "source_clause_id": "budget:line-1",
                "compared_values": {"contract": 1_600_000.0, "budget": 1_200_000.0},
                "delta": 400_000.0,
                "direction": "contract_exceeds_budget",
            }
        ],
        evidence_certainty=certainty,
    )


@pytest.fixture
def aggregator() -> CategoryAggregator:
    return CategoryAggregator(CategoryStateMachine())


def _score(agg: CategoryAggregator, conflict: ConflictReport,
           base_signal: float = 100.0) -> float:
    cat: CategoryV2 = agg.aggregate(
        category="BUDGET",
        evidence=_bundle(),
        conflict=conflict,
        rule_signals=[("DET-BUD-SUM", base_signal)],
        applicable=True,
    )
    assert cat.coherence_score is not None, "a hard conflict must still yield a numeric score"
    return cat.coherence_score


# ---------------------------------------------------------------------------
# CHARACTERIZATION — invariants the current code already honors (must not regress)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_conflicting_evidence_state_is_decoupled_from_zero(aggregator: CategoryAggregator) -> None:
    """§A: `conflicting_evidence` is a STATE; the score is not forced to 0."""
    cat = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(),
        conflict=_conflict("critical", 1.0),
        rule_signals=[("DET-BUD-SUM", 100.0)],
        applicable=True,
    )
    assert cat.status is CategoryStatus.CONFLICTING_EVIDENCE
    assert cat.coherence_score is not None
    assert cat.coherence_score > 0.0, "critical conflict must NOT force score = 0 (incoherence != falsehood)"


@pytest.mark.unit
def test_critical_conflict_scores_worse_than_clean_comparable(aggregator: CategoryAggregator) -> None:
    """§B: more severe / material incoherence can never IMPROVE the score."""
    clean = _score(aggregator, _no_conflict())
    conflicted = _score(aggregator, _conflict("critical", 1.0))
    assert conflicted < clean


@pytest.mark.unit
def test_severity_is_monotonic(aggregator: CategoryAggregator) -> None:
    """§B: worse severity => lower-or-equal score, holding certainty fixed."""
    crit = _score(aggregator, _conflict("critical", 1.0))
    high = _score(aggregator, _conflict("high", 1.0))
    assert crit <= high


# ---------------------------------------------------------------------------
# RED — the ratified invariant the current v2 formula VIOLATES (Phase-1a target)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_higher_certainty_yields_stronger_penalty(aggregator: CategoryAggregator) -> None:
    """§D: detection-certainty scales the PENALTY, not the score.

    Higher certainty => stronger penalty => lower (or equal) score. The current
    `adjusted = base × severity × certainty` is INVERTED: a more-certain conflict
    scores HIGHER. This test is expected RED until the formula is corrected.
    """
    more_certain = _score(aggregator, _conflict("critical", 1.0))
    less_certain = _score(aggregator, _conflict("critical", 0.9))
    assert more_certain <= less_certain, (
        f"more-certain critical ({more_certain}) must not out-score "
        f"less-certain critical ({less_certain}) — certainty scales the penalty"
    )
