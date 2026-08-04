"""
Deterministic conflict detection service (ADR-009 §6, §9).

Phase 1 scope: cross-reference checks only — no LLM-driven inference.
Returns a `ConflictReport` consumed by the category aggregator.

Refers to Suite ID: TS-UA-COH-V2-CONFLICT-001.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from src.coherence.models import FindingSignal
from src.coherence.services.v2.evidence_service import EvidenceBundle

ConflictSeverity = Literal["none", "low", "medium", "high", "critical"]

# ADR-009 §4.2 distinguishes strong conflicts needing review (high) from
# critical incoherence validated with high algorithmic certainty (critical).
# A >20% mismatch is materially beyond ordinary reconciliation tolerance. A
# 0.90 certainty floor prevents an uncertain candidate from imposing a harsher
# category penalty than a verified contradiction.
CRITICAL_MISMATCH_RATIO = 0.20
HARD_CONFLICT_MINIMUM_DETERMINISTIC_CERTAINTY = 0.90


@dataclass(frozen=True)
class ConflictReport:
    severity: ConflictSeverity
    hard_conflict: bool
    conflict_set: list[dict[str, Any]] = field(default_factory=list)
    evidence_certainty: float = 1.0


@dataclass(frozen=True)
class ConflictCandidate:
    """PII-minimized deterministic evidence for a possible hard contradiction.

    This intentionally carries no clause quote, evidence summary, item names, or
    arbitrary evaluator ``raw_data``.  ``source_document_id`` is optional because
    the current ``FindingSignal``/``Clause`` contract only guarantees clause-level
    provenance; extraction may populate it when available.

    Refers to Suite ID: TS-UA-COH-V2-CONFLICT-LEDGER-001.
    """

    rule_id: str
    category: str
    source_clause_id: str
    compared_values: dict[str, float]
    delta: float
    direction: str
    deterministic_certainty: float
    source_document_id: str | None = None


_CONTRADICTION_VALUE_KEYS: dict[str, tuple[str, str]] = {
    "DET-BUD-SUM": ("items_sum", "contract_total"),
    "DET-BUD-INTERNAL": ("items_sum", "stated_total"),
    "DET-CRS-SCPBUD": ("unfunded_count", "total_deliverables"),
    "DET-TEC-BOMBUDGET": ("unlinked_count", "total"),
}


def build_conflict_candidates(signals: Iterable[FindingSignal]) -> list[ConflictCandidate]:
    """Project true deterministic cross-value findings into a safe conflict ledger."""
    candidates: list[ConflictCandidate] = []
    for signal in signals:
        value_keys = _CONTRADICTION_VALUE_KEYS.get(signal.rule_id)
        if signal.source != "deterministic" or value_keys is None:
            continue

        raw_data = signal.raw_data
        left_key, right_key = value_keys
        left_value = _candidate_value(raw_data, left_key)
        right_value = _candidate_value(raw_data, right_key)
        if left_value is None or right_value is None:
            continue

        delta = left_value - right_value
        direction = raw_data.get("direction")
        if not isinstance(direction, str) or not direction:
            direction = "exceeds" if delta > 0 else "below" if delta < 0 else "matches"

        source_document_id = raw_data.get("source_document_id") or raw_data.get("document_id")
        candidates.append(
            ConflictCandidate(
                rule_id=signal.rule_id,
                category=signal.category,
                source_clause_id=signal.clause_id,
                source_document_id=(
                    str(source_document_id) if source_document_id is not None else None
                ),
                compared_values={left_key: left_value, right_key: right_value},
                delta=delta,
                direction=direction,
                deterministic_certainty=signal.confidence,
            )
        )
    return candidates


def _candidate_value(raw_data: dict[str, Any], key: str) -> float | None:
    """Read a numeric comparison value without copying raw labels into the ledger."""
    value = raw_data.get(key)
    if key == "unfunded_count" and not isinstance(value, int | float):
        unfunded = raw_data.get("unfunded")
        if isinstance(unfunded, list):
            value = len(unfunded)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


class ConflictService:
    """Detects hard cross-document contradictions deterministically.

    Refers to Suite ID: TS-UA-COH-V2-CONFLICT-001.
    """

    def detect(  # noqa: D401 — Protocol-style stub
        self,
        category: str,
        evidence: EvidenceBundle,
        candidates: list[ConflictCandidate],
    ) -> ConflictReport:
        del evidence
        category_candidates = [candidate for candidate in candidates if candidate.category == category]
        confirmed_candidates = [
            candidate
            for candidate in category_candidates
            if _bounded_certainty(candidate.deterministic_certainty)
            >= HARD_CONFLICT_MINIMUM_DETERMINISTIC_CERTAINTY
        ]
        if not confirmed_candidates:
            return ConflictReport(
                severity="none", hard_conflict=False, conflict_set=[], evidence_certainty=1.0
            )

        evidence_certainty = max(
            _bounded_certainty(candidate.deterministic_certainty)
            for candidate in confirmed_candidates
        )
        severity: ConflictSeverity = (
            "critical"
            if any(_is_critical(candidate) for candidate in confirmed_candidates)
            else "high"
        )
        return ConflictReport(
            severity=severity,
            hard_conflict=True,
            conflict_set=[_sanitize_candidate(candidate) for candidate in confirmed_candidates],
            evidence_certainty=evidence_certainty,
        )


def _is_critical(candidate: ConflictCandidate) -> bool:
    """Return whether a candidate clears the ADR-009 critical evidence threshold."""
    values = tuple(candidate.compared_values.values())
    denominator = max((abs(value) for value in values), default=0.0)
    mismatch_ratio = abs(candidate.delta) / denominator if denominator else 0.0
    return (
        mismatch_ratio > CRITICAL_MISMATCH_RATIO
        and _bounded_certainty(candidate.deterministic_certainty)
        >= HARD_CONFLICT_MINIMUM_DETERMINISTIC_CERTAINTY
    )


def _bounded_certainty(certainty: float) -> float:
    """Defensively bound deterministic certainty before it affects a score."""
    return max(0.0, min(1.0, certainty))


def _sanitize_candidate(candidate: ConflictCandidate) -> dict[str, Any]:
    """Return alert-safe conflict evidence without quotes, summaries, or item labels."""
    conflict: dict[str, Any] = {
        "rule_id": candidate.rule_id,
        "source_clause_id": candidate.source_clause_id,
        "compared_values": candidate.compared_values,
        "delta": candidate.delta,
        "direction": candidate.direction,
    }
    if candidate.source_document_id is not None:
        conflict["source_document_id"] = candidate.source_document_id
    return conflict


__all__ = [
    "ConflictCandidate",
    "ConflictReport",
    "ConflictService",
    "ConflictSeverity",
    "build_conflict_candidates",
]
