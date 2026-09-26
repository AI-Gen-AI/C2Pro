"""
Adapter: `CrossDocFinding` → `FindingSignal` (ADR-023 Phase 1b).

Bridges a first-class cross-document finding onto the existing deterministic-signal
contract so it flows through `build_conflict_candidates` → `ConflictService` →
`CategoryAggregator` → the canonical scorer. The `raw_data` carries the compared
values / delta / direction the conflict ledger reads; downstream severity is derived
from the materiality ratio by the conflict service (so it is not hard-coded here — we
only set the v1 `severity`/`impact_score` fields the legacy path still consumes).

Refers to Suite ID: TS-UA-COH-XDOC-ADAPTER-001.
"""
from __future__ import annotations

from src.coherence.cross_document.findings import CrossDocFinding
from src.coherence.models import FindingSignal, SeverityLevel

# Aligns with conflict_service.CRITICAL_MISMATCH_RATIO — a discrepancy above this reads
# as critical. Kept as a local mirror so this adapter has no import cycle; the conflict
# service remains the authority that actually classifies the v2 conflict severity.
_CRITICAL_MISMATCH_RATIO = 0.20


def _v1_severity(materiality_ratio: float) -> SeverityLevel:
    return "critical" if materiality_ratio > _CRITICAL_MISMATCH_RATIO else "high"


def to_finding_signal(finding: CrossDocFinding) -> FindingSignal:
    """Map a cross-document finding onto the deterministic FindingSignal contract."""
    return FindingSignal(
        rule_id=finding.rule_id,
        clause_id=f"xdoc:{finding.rule_id}",  # synthetic: a cross-doc finding spans clauses
        source="deterministic",
        impact_score=min(1.0, 0.5 + finding.materiality_ratio),
        confidence=1.0,  # deterministic ⇒ clears the hard-conflict certainty floor
        severity=_v1_severity(finding.materiality_ratio),
        category=finding.category,
        evidence_summary=finding.summary,
        quote="",
        raw_data={
            **finding.compared_values,
            "delta": finding.delta,
            "direction": finding.direction,
            "materiality_ratio": finding.materiality_ratio,
        },
    )


__all__ = ["to_finding_signal"]
