"""
Calibration report assembler (ADR-009 §G, §21).

Combines the pure metrics into a single `CalibrationReport`. The report is
**descriptive**: it computes the multi-metric picture (critical precision / recall /
FPR, score MAE + correlation vs expert, null-behaviour) but does NOT itself decide
cutover — the must-pass thresholds are applied by the gate on top, once a real expert
corpus is supplied. MAE is one entry, never the sole criterion (§G).

Refers to Suite ID: TS-UA-COH-CALIB-REPORT-001.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from src.coherence.calibration.metrics import (
    ConfusionMatrix,
    mean_absolute_error,
    pearson_correlation,
)


@dataclass(frozen=True)
class CalibrationReport:
    """The multi-metric calibration picture for a corpus run (descriptive, not a verdict)."""

    critical_findings: ConfusionMatrix
    score_mae: float | None
    score_correlation: float | None
    null_behaviour_ok: bool
    project_count: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_count": self.project_count,
            "critical_precision": self.critical_findings.precision,
            "critical_recall": self.critical_findings.recall,
            "critical_false_positive_rate": self.critical_findings.false_positive_rate,
            "critical_f1": self.critical_findings.f1,
            "score_mae": self.score_mae,
            "score_correlation": self.score_correlation,
            "null_behaviour_ok": self.null_behaviour_ok,
            "notes": list(self.notes),
        }


def build_report(
    critical_labels: Iterable[tuple[bool, bool]],
    predicted_scores: Sequence[float | None],
    expert_scores: Sequence[float | None],
    *,
    null_behaviour_ok: bool = True,
    project_count: int = 0,
    notes: Iterable[str] = (),
) -> CalibrationReport:
    """Assemble a report from extracted labels + scores.

    Args:
        critical_labels: `(predicted_critical, actually_critical)` per candidate finding.
        predicted_scores / expert_scores: aligned per-project scores (either may be None).
        null_behaviour_ok: whether every no-evidence category scored None (never 0).
        project_count: number of projects in the corpus run.
        notes: free-form annotations (e.g. corpus provenance, excluded gaps).
    """
    return CalibrationReport(
        critical_findings=ConfusionMatrix.from_labels(critical_labels),
        score_mae=mean_absolute_error(predicted_scores, expert_scores),
        score_correlation=pearson_correlation(predicted_scores, expert_scores),
        null_behaviour_ok=null_behaviour_ok,
        project_count=project_count,
        notes=tuple(notes),
    )


__all__ = ["CalibrationReport", "build_report"]
