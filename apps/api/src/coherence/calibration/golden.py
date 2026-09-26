"""
Expert / golden ground-truth schema for coherence calibration (ADR-009 §G).

A golden corpus is a list of `GoldenProject`: the expert's overall coherence judgement
plus the findings the expert considers real (`is_true_positive=True`) or explicitly
NOT real (`is_true_positive=False` — a known false positive the engine must not raise).
This schema is what a real corpus (e.g. an anonymized expert-reviewed set) is loaded
into; nothing here fabricates values.

Refers to Suite ID: TS-UD-COH-CALIB-GOLDEN-001.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenFinding:
    """One expert-labelled finding for a project."""

    category: str
    severity: str
    is_true_positive: bool = True  # False ⇒ a known false positive the engine should NOT raise


@dataclass(frozen=True)
class GoldenProject:
    """Expert ground truth for a single project."""

    project_id: str
    expert_score: float | None  # expert's overall coherence judgement (None if unscored)
    findings: tuple[GoldenFinding, ...] = field(default_factory=tuple)

    @property
    def true_findings(self) -> tuple[GoldenFinding, ...]:
        return tuple(f for f in self.findings if f.is_true_positive)

    @property
    def false_findings(self) -> tuple[GoldenFinding, ...]:
        return tuple(f for f in self.findings if not f.is_true_positive)


__all__ = ["GoldenFinding", "GoldenProject"]
