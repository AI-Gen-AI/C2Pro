"""TS-UD-HEALTH-018-004 - Coherence is a Contract health subscore only."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.application.coherence_subscore import coherence_subscore_from_result
from src.health.application.contract_scorer import score_contract_dimension
from src.health.domain.health_vector import HealthBand, HealthDimension
from src.project_state.domain.entities import Clause, Obligation


def _evidence(ref_id: str) -> EvidenceRef:
    return EvidenceRef(
        ref_id=ref_id,
        source="contract",
        tier=EvidenceTier.VERIFIED,
        locator=ref_id,
    )


def _clause(index: int) -> Clause:
    code = f"{index}.0"
    return Clause(
        entity_id=uuid4(),
        clause_id=code,
        text=f"Clause {code} text",
        evidence=[_evidence(f"clause-{code}")],
    )


def _obligation(index: int, clause_id: str = "1.0") -> Obligation:
    return Obligation(
        entity_id=uuid4(),
        description=f"Obligation {index}",
        clause_id=clause_id,
        evidence=[_evidence(f"obligation-{index}")],
    )


def _coherence_result(overall_score: float | None) -> ProjectCoherenceResult:
    return ProjectCoherenceResult(
        overall_score=overall_score,
        category_scores={},
        signal_count=3,
        finding_count=1,
        artifact_count=2,
        llm_on=False,
    )


def test_coherence_subscore_extracts_and_normalizes_overall_score() -> None:
    assert coherence_subscore_from_result(_coherence_result(82)) == 82
    assert coherence_subscore_from_result(_coherence_result(0.82)) == 82
    assert coherence_subscore_from_result(_coherence_result(None)) is None
    assert coherence_subscore_from_result(None) is None


def test_coherence_is_not_a_health_dimension() -> None:
    assert "COHERENCE" not in HealthDimension.__members__


def test_contract_dimension_consumes_coherence_as_subscore() -> None:
    clauses = [_clause(index) for index in range(1, 6)]
    obligations = [_obligation(1), _obligation(2)]

    signal = score_contract_dimension(
        clauses,
        obligations,
        coherence_subscore=coherence_subscore_from_result(_coherence_result(0.9)),
    )

    assert signal.dimension is HealthDimension.CONTRACT
    assert signal.score == pytest.approx(88.6)
    assert signal.band is HealthBand.HEALTHY
    assert any(ref.source == "project_coherence" for ref in signal.evidence)


def test_missing_coherence_keeps_contract_scored_from_contract_evidence_only() -> None:
    signal = score_contract_dimension(
        [_clause(1)],
        [],
        coherence_subscore=coherence_subscore_from_result(None),
    )

    assert signal.dimension is HealthDimension.CONTRACT
    assert signal.score == pytest.approx(52)
    assert signal.band is HealthBand.AT_RISK
    assert "coherence subscore unavailable" in signal.missing_data
    assert signal.evidence
