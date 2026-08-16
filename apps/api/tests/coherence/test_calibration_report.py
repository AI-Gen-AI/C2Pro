"""
Calibration report assembler + golden schema (ADR-009 §G).

Refers to Suite ID: TS-UA-COH-CALIB-REPORT-001.
"""
from __future__ import annotations

import pytest

from src.coherence.calibration.golden import GoldenFinding, GoldenProject
from src.coherence.calibration.report import build_report


@pytest.mark.unit
def test_golden_project_splits_true_and_false_findings() -> None:
    project = GoldenProject(
        project_id="p1",
        expert_score=80.0,
        findings=(
            GoldenFinding("BUDGET", "critical", is_true_positive=True),
            GoldenFinding("LEGAL", "high", is_true_positive=False),
        ),
    )
    assert [f.category for f in project.true_findings] == ["BUDGET"]
    assert [f.category for f in project.false_findings] == ["LEGAL"]


@pytest.mark.unit
def test_build_report_combines_metrics() -> None:
    report = build_report(
        critical_labels=[(True, True), (True, False), (False, True)],
        predicted_scores=[90.0, 55.0, None],
        expert_scores=[85.0, 60.0, 70.0],
        null_behaviour_ok=True,
        project_count=3,
        notes=["seed corpus"],
    )
    assert report.critical_findings.precision == pytest.approx(0.5)  # tp1 / (tp1+fp1)
    assert report.critical_findings.recall == pytest.approx(0.5)  # tp1 / (tp1+fn1)
    assert report.score_mae == pytest.approx((5 + 5) / 2)  # (|90-85|+|55-60|)/2
    assert report.score_correlation is not None
    assert report.null_behaviour_ok is True
    assert report.project_count == 3


@pytest.mark.unit
def test_report_as_dict_exposes_all_axes() -> None:
    report = build_report(
        critical_labels=[(True, True)],
        predicted_scores=[80.0],
        expert_scores=[80.0],
        project_count=1,
    )
    d = report.as_dict()
    assert set(d) >= {
        "critical_precision",
        "critical_recall",
        "critical_false_positive_rate",
        "score_mae",
        "score_correlation",
        "null_behaviour_ok",
        "project_count",
    }
    assert d["critical_precision"] == pytest.approx(1.0)
    assert d["score_mae"] == pytest.approx(0.0)
