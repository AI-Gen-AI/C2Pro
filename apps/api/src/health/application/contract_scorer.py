"""TS-UD-HEALTH-018-002 - Deterministic contract health scorer.

Formula v0:
- no extracted contract evidence returns honest-null.
- base score = 45 + 35 * clause_coverage + 20 * obligation_factor.
- optional coherence is normalized to 0-100 and blended at 30 percent.
  Coherence is a contract subscore, not a standalone health dimension.
"""

from __future__ import annotations

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    band_for_score,
)
from src.project_state.domain.entities import Clause, Obligation

_FULL_COVERAGE_CLAUSE_COUNT = 5


def score_contract_dimension(
    clauses: list[Clause],
    obligations: list[Obligation],
    *,
    coherence_subscore: float | None = None,
) -> HealthSignal:
    """Score contract health from extracted clauses, obligations, and coherence."""

    if not clauses and not obligations:
        return HealthSignal(
            dimension=HealthDimension.CONTRACT,
            score=None,
            band=HealthBand.UNKNOWN,
            confidence=0.0,
            missing_data=["no contract clauses extracted"],
            null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        )

    clause_coverage = min(1.0, len(clauses) / _FULL_COVERAGE_CLAUSE_COUNT)
    obligation_factor = min(1.0, len(obligations) / max(len(clauses), 1))
    base_score = 45.0 + (35.0 * clause_coverage) + (20.0 * obligation_factor)
    missing_data: list[str] = []
    evidence = _contract_evidence(clauses, obligations)

    if coherence_subscore is None:
        score = base_score
        missing_data.append("coherence subscore unavailable")
        confidence = _contract_confidence(
            clause_coverage=clause_coverage,
            obligation_factor=obligation_factor,
            coherence_available=False,
        )
    else:
        coherence_score = _normalize_coherence_score(coherence_subscore)
        score = (0.70 * base_score) + (0.30 * coherence_score)
        confidence = _contract_confidence(
            clause_coverage=clause_coverage,
            obligation_factor=obligation_factor,
            coherence_available=True,
        )
        evidence.append(
            EvidenceRef(
                ref_id="project-coherence-subscore",
                source="project_coherence",
                tier=EvidenceTier.WEAK,
                locator="overall_score",
            )
        )

    score = min(100.0, max(0.0, score))
    return HealthSignal(
        dimension=HealthDimension.CONTRACT,
        score=score,
        band=band_for_score(score),
        confidence=confidence,
        evidence=evidence,
        missing_data=missing_data,
    )


def _normalize_coherence_score(coherence_subscore: float) -> float:
    if coherence_subscore <= 1.0:
        return min(100.0, max(0.0, coherence_subscore * 100.0))
    return min(100.0, max(0.0, coherence_subscore))


def _contract_confidence(
    *,
    clause_coverage: float,
    obligation_factor: float,
    coherence_available: bool,
) -> float:
    confidence = 0.45 + (0.35 * clause_coverage) + (0.10 * obligation_factor)
    if not coherence_available:
        confidence -= 0.15
    return round(min(0.90, max(0.0, confidence)), 2)


def _contract_evidence(clauses: list[Clause], obligations: list[Obligation]) -> list[EvidenceRef]:
    evidence: list[EvidenceRef] = []
    for clause in clauses:
        if clause.evidence:
            evidence.extend(clause.evidence)
        else:
            evidence.append(
                EvidenceRef(
                    ref_id=clause.clause_id,
                    source="contract_clause",
                    tier=EvidenceTier.WEAK,
                    locator=clause.clause_id,
                )
            )
    for obligation in obligations:
        if obligation.evidence:
            evidence.extend(obligation.evidence)
        else:
            evidence.append(
                EvidenceRef(
                    ref_id=str(obligation.entity_id),
                    source="contract_obligation",
                    tier=EvidenceTier.WEAK,
                    locator=obligation.clause_id,
                )
            )
    return evidence


__all__ = ["score_contract_dimension"]
