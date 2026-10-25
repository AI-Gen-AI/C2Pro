"""
Typed result of a cross-document comparison (ADR-023 Phase 1b).

Carries the two compared values, their delta/direction and the materiality ratio.
The `compared_values` / `delta` / `direction` shape matches the conflict ledger
(`build_conflict_candidates`) so a finding maps cleanly onto a deterministic
`FindingSignal` and flows into the canonical scorer.

Refers to Suite ID: TS-UD-COH-XDOC-FINDING-001.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.coherence.models import CoherenceCategory


@dataclass(frozen=True)
class CrossDocFinding:
    """A material discrepancy found between two documents' values."""

    rule_id: str  # e.g. DET-CRS-CONBUD
    category: CoherenceCategory  # coherence category the discrepancy scores against
    left_key: str
    left_value: float
    right_key: str
    right_value: float
    delta: float  # left_value - right_value
    direction: str  # "exceeds" | "below"
    materiality_ratio: float  # |delta| / max(|left|, |right|)
    summary: str
    # Optional traceability for findings built from sourced evidence (dates): the clause the
    # alert should point at, and the expected/observed sources (document, revision, locator).
    source_clause_id: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def compared_values(self) -> dict[str, float]:
        return {self.left_key: self.left_value, self.right_key: self.right_value}


@dataclass(frozen=True)
class CrossDocNotAssessed:
    """A comparison that was deliberately not made, with the reason why.

    Not a finding: it carries no values to score and never becomes a signal.
    """

    rule_id: str
    # "CURRENCY_MISMATCH" | "MIXED_CURRENCY" | "DATE_KIND_NOT_COMPARABLE" | "UNSOURCED_DATE"
    # | "AMBIGUOUS_DATE" | "DATE_NOT_ASSESSED"
    reason: str
    left_key: str
    right_key: str
    detail: str
    state: str = "NOT_ASSESSED"


@dataclass(frozen=True)
class CrossDocProvisional:
    """A possible deviation whose evidence is an observation, not an approved baseline.

    The dates and their sources are preserved exactly, but this is NOT a confirmed breach: it never
    becomes a scoring signal (no 1.0 confidence, no TRUSTED Coherence Score input). It is shown as a
    provisional risk with its evidence and an honest state.
    """

    rule_id: str
    category: CoherenceCategory
    left_key: str
    left_value: float
    right_key: str
    right_value: float
    delta: float
    summary: str
    source_clause_id: str | None
    evidence: Mapping[str, Any]
    reason: str = "SCHEDULE_NOT_APPROVED_BASELINE"
    state: str = "PROVISIONAL"


__all__ = ["CrossDocFinding", "CrossDocNotAssessed", "CrossDocProvisional"]
