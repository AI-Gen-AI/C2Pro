"""
Calibration machinery for the canonical coherence scorer (ADR-009 §G, §21).

The **real, multi-metric calibration gate** — NOT v1↔v2 MAE alone. This package holds
the pure, corpus-independent pieces:

- `golden`  — the expert/golden ground-truth schema a corpus is expressed in.
- `metrics` — pure metric math: confusion matrix (precision / recall / FPR / F1),
  score MAE and Pearson correlation vs expert judgement.
- `report`  — assembles the computed metrics into a `CalibrationReport`.

Extraction (running v1 + canonical-v2 over a real corpus to produce predicted
findings/scores) and the must-pass thresholds plug in on top once an expert corpus is
supplied — this module deliberately invents no ground truth.
"""
from __future__ import annotations

from src.coherence.calibration.gate import EngineRun, evaluate_against_golden
from src.coherence.calibration.gemini_adapter import (
    alert_category,
    gemini_budget_inputs,
    gemini_expected_categories,
    gemini_to_golden_project,
)
from src.coherence.calibration.golden import GoldenFinding, GoldenProject
from src.coherence.calibration.golden_loader import load_golden, parse_golden
from src.coherence.calibration.metrics import (
    ConfusionMatrix,
    mean_absolute_error,
    pearson_correlation,
)
from src.coherence.calibration.report import CalibrationReport, build_report
from src.coherence.calibration.shadow_compare import ProjectRun, compare_runs

__all__ = [
    "CalibrationReport",
    "ConfusionMatrix",
    "EngineRun",
    "GoldenFinding",
    "GoldenProject",
    "ProjectRun",
    "alert_category",
    "build_report",
    "compare_runs",
    "evaluate_against_golden",
    "gemini_budget_inputs",
    "gemini_expected_categories",
    "gemini_to_golden_project",
    "load_golden",
    "mean_absolute_error",
    "parse_golden",
    "pearson_correlation",
]
