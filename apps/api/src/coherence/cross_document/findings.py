"""
Typed result of a cross-document comparison (ADR-023 Phase 1b).

Carries the two compared values, their delta/direction and the materiality ratio.
The `compared_values` / `delta` / `direction` shape matches the conflict ledger
(`build_conflict_candidates`) so a finding maps cleanly onto a deterministic
`FindingSignal` and flows into the canonical scorer.

Refers to Suite ID: TS-UD-COH-XDOC-FINDING-001.
"""
from __future__ import annotations

from dataclasses import dataclass

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

    @property
    def compared_values(self) -> dict[str, float]:
        return {self.left_key: self.left_value, self.right_key: self.right_value}


__all__ = ["CrossDocFinding"]
