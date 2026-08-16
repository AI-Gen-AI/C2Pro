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

from src.coherence.calibration.golden import GoldenFinding, GoldenProject
from src.coherence.calibration.metrics import (
    ConfusionMatrix,
    mean_absolute_error,
    pearson_correlation,
)
from src.coherence.calibration.report import CalibrationReport, build_report

__all__ = [
    "CalibrationReport",
    "ConfusionMatrix",
    "GoldenFinding",
    "GoldenProject",
    "build_report",
    "mean_absolute_error",
    "pearson_correlation",
]
