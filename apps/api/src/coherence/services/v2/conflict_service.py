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
    """Detects hard cross-document contradictions deterministically."""

    def detect(  # noqa: D401 — Protocol-style stub
        self,
        category: str,
        evidence: EvidenceBundle,
        candidates: list[ConflictCandidate],
    ) -> ConflictReport:
        # Phase 1: no deterministic rule emits hard conflicts yet — wired in
        # Phase 3 once the cross-document ledger lands. Default = no conflict.
        del category, evidence, candidates
        return ConflictReport(
            severity="none", hard_conflict=False, conflict_set=[], evidence_certainty=1.0
        )


__all__ = [
    "ConflictCandidate",
    "ConflictReport",
    "ConflictService",
    "ConflictSeverity",
    "build_conflict_candidates",
]
