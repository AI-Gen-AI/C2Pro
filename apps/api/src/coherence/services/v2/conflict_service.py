"""
Deterministic conflict detection service (ADR-009 §6, §9).

Phase 1 scope: cross-reference checks only — no LLM-driven inference.
Returns a `ConflictReport` consumed by the category aggregator.

Refers to Suite ID: TS-UA-COH-V2-CONFLICT-001.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.coherence.services.v2.evidence_service import EvidenceBundle

ConflictSeverity = Literal["none", "low", "medium", "high", "critical"]


@dataclass(frozen=True)
class ConflictReport:
    severity: ConflictSeverity
    hard_conflict: bool
    conflict_set: list[dict[str, Any]] = field(default_factory=list)
    evidence_certainty: float = 1.0


class ConflictService:
    """Detects hard cross-document contradictions deterministically."""

    def detect(  # noqa: D401 — Protocol-style stub
        self,
        category: str,
        evidence: EvidenceBundle,
        rule_signals: list[tuple[str, float]],
    ) -> ConflictReport:
        # Phase 1: no deterministic rule emits hard conflicts yet — wired in
        # Phase 3 once the cross-document ledger lands. Default = no conflict.
        del category, evidence, rule_signals
        return ConflictReport(
            severity="none", hard_conflict=False, conflict_set=[], evidence_certainty=1.0
        )


__all__ = ["ConflictReport", "ConflictService", "ConflictSeverity"]
