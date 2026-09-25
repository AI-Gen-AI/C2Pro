"""
Shadow-mode comparison (ADR-009 §G, §21).

Compares the canonical (v2) scoring against the current live (v1) path over a corpus
and produces the multi-metric `CalibrationReport` via the pure calibration machinery.

Until an expert/golden corpus exists, **v1 is the INTERIM reference** — so the report
measures v2↔v1 *divergence*, not correctness. Swapping v1 for expert ground truth turns
the exact same report into a real precision/recall cutover gate (that swap is what the
Abengoa investigation feeds).

Refers to Suite ID: TS-UA-COH-CALIB-SHADOW-001.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from src.coherence.calibration.report import CalibrationReport, build_report

_DEFAULT_CATEGORIES: tuple[str, ...] = (
    "SCOPE",
    "BUDGET",
    "TIME",
    "TECHNICAL",
    "LEGAL",
    "QUALITY",
)


@dataclass(frozen=True)
class ProjectRun:
    """One project scored by both paths, with the categories each flagged."""

    project_id: str
    v1_score: float | None
    v2_score: float | None
    v1_flagged: frozenset[str] = field(default_factory=frozenset)
    v2_flagged: frozenset[str] = field(default_factory=frozenset)


def compare_runs(
    runs: Iterable[ProjectRun],
    *,
    categories: Sequence[str] = _DEFAULT_CATEGORIES,
    null_behaviour_ok: bool = True,
) -> CalibrationReport:
    """Build a shadow report: v2-vs-v1 score agreement + per-category flag agreement.

    v1 is the interim reference (`expected`); the confusion matrix therefore measures
    v2↔v1 agreement (a v2-only flag is a "false positive" vs v1), not correctness, until
    an expert golden corpus replaces v1.
    """
    materialized = list(runs)
    v1_scores = [run.v1_score for run in materialized]
    v2_scores = [run.v2_score for run in materialized]

    labels: list[tuple[bool, bool]] = []
    for run in materialized:
        for category in categories:
            predicted = category in run.v2_flagged
            actual = category in run.v1_flagged
            labels.append((predicted, actual))

    return build_report(
        critical_labels=labels,
        predicted_scores=v2_scores,
        expert_scores=v1_scores,
        null_behaviour_ok=null_behaviour_ok,
        project_count=len(materialized),
        notes=(
            "shadow mode: v1 is the interim reference — measures v2<->v1 divergence, "
            "not correctness; swap for the expert golden corpus to gate cutover",
        ),
    )


__all__ = ["ProjectRun", "compare_runs"]
