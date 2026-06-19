"""TS-UD-HEALTH-018-002 - Contract health scorer honest-null behavior."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.application.contract_scorer import score_contract_dimension
from src.health.domain.health_vector import HealthBand, HealthDimension, HealthNullReason
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


def test_no_contract_clauses_is_unknown_not_green() -> None:
    signal = score_contract_dimension([], [])

    assert signal.dimension is HealthDimension.CONTRACT
    assert signal.score is None
    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE
    assert "no contract clauses extracted" in signal.missing_data
    assert signal.confidence == 0


def test_contract_score_blends_clause_coverage_obligations_and_coherence() -> None:
    clauses = [_clause(index) for index in range(1, 6)]
    obligations = [_obligation(1), _obligation(2)]

    signal = score_contract_dimension(clauses, obligations, coherence_subscore=0.9)

    assert signal.score == pytest.approx(88.6)
    assert signal.band is HealthBand.HEALTHY
    assert signal.confidence == pytest.approx(0.84)
    assert len(signal.evidence) == 8
    assert not signal.missing_data


def test_contract_score_without_coherence_stays_conservative() -> None:
    signal = score_contract_dimension([_clause(1)], [], coherence_subscore=None)

    assert signal.score == pytest.approx(52)
    assert signal.band is HealthBand.AT_RISK
    assert signal.confidence == pytest.approx(0.37)
    assert "coherence subscore unavailable" in signal.missing_data
    assert signal.evidence
