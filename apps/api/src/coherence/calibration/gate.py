"""
Calibration gate — score the engine against the EXPERT golden corpus (ADR-009 §G, §21).

Where `shadow_compare` uses v1 as an interim reference, this compares the engine against
**expert ground truth**: per-category flag precision / recall / FPR (did the engine raise a
finding where the expert says there's a real one?) plus engine-score↔expert-score MAE and
correlation.

`detectable_categories` scopes the confusion matrix to the finding types the deterministic
engine can actually catch, so qualitative expert findings (risk-narrative, legal exposure)
don't artificially depress recall — those are tracked as known gaps, not gate failures.

Refers to Suite ID: TS-UA-COH-CALIB-GATE-001.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from src.coherence.calibration.golden import GoldenProject
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
class EngineRun:
    """What the engine produced for one project: overall score + flagged categories."""

    project_id: str
    score: float | None
    flagged_categories: frozenset[str] = field(default_factory=frozenset)


def evaluate_against_golden(
    runs: Iterable[EngineRun],
    golden: Iterable[GoldenProject],
    *,
    detectable_categories: Sequence[str] = _DEFAULT_CATEGORIES,
) -> CalibrationReport:
    """Score engine runs against the expert golden, matched by ``project_id``.

    Only projects present in BOTH runs and golden are scored. The confusion matrix is
    built over ``detectable_categories`` only (predicted = engine flagged the category;
    actual = the golden has a *true-positive* finding in it).
    """
    golden_by_id = {g.project_id: g for g in golden}
    predicted_scores: list[float | None] = []
    expert_scores: list[float | None] = []
    labels: list[tuple[bool, bool]] = []
    matched = 0

    for run in runs:
        golden_project = golden_by_id.get(run.project_id)
        if golden_project is None:
            continue
        matched += 1
        predicted_scores.append(run.score)
        expert_scores.append(golden_project.expert_score)
        true_categories = {finding.category for finding in golden_project.true_findings}
        for category in detectable_categories:
            labels.append(
                (category in run.flagged_categories, category in true_categories)
            )

    return build_report(
        critical_labels=labels,
        predicted_scores=predicted_scores,
        expert_scores=expert_scores,
        project_count=matched,
        notes=(
            f"engine vs expert golden over {matched} matched project(s); confusion "
            f"scoped to detectable categories {tuple(detectable_categories)}",
        ),
    )


__all__ = ["EngineRun", "evaluate_against_golden"]
