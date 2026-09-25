"""
Shadow-mode comparison harness (ADR-009 §G).

Refers to Suite ID: TS-UA-COH-CALIB-SHADOW-001.
"""
from __future__ import annotations

import pytest

from src.coherence.calibration import ProjectRun, compare_runs


@pytest.mark.unit
def test_perfect_agreement_scores_and_flags() -> None:
    runs = [
        ProjectRun("p1", v1_score=90.0, v2_score=90.0),
        ProjectRun(
            "p2",
            v1_score=50.0,
            v2_score=50.0,
            v1_flagged=frozenset({"BUDGET"}),
            v2_flagged=frozenset({"BUDGET"}),
        ),
    ]
    report = compare_runs(runs)
    assert report.score_mae == pytest.approx(0.0)
    assert report.score_correlation == pytest.approx(1.0)
    assert report.critical_findings.precision == pytest.approx(1.0)
    assert report.critical_findings.recall == pytest.approx(1.0)
    assert report.project_count == 2


@pytest.mark.unit
def test_v2_only_flag_is_false_positive_vs_v1() -> None:
    runs = [
        ProjectRun(
            "p1",
            v1_score=90.0,
            v2_score=60.0,
            v1_flagged=frozenset({"BUDGET"}),
            v2_flagged=frozenset({"BUDGET", "LEGAL"}),
        )
    ]
    report = compare_runs(runs)
    assert report.score_mae == pytest.approx(30.0)  # |60 - 90|
    assert report.critical_findings.tp == 1  # BUDGET flagged by both
    assert report.critical_findings.fp == 1  # LEGAL flagged only by v2


@pytest.mark.unit
def test_null_scores_excluded_from_mae() -> None:
    runs = [
        ProjectRun("p1", v1_score=None, v2_score=80.0),  # v1 withheld → excluded
        ProjectRun("p2", v1_score=70.0, v2_score=72.0),
    ]
    report = compare_runs(runs)
    assert report.score_mae == pytest.approx(2.0)
    assert report.project_count == 2


@pytest.mark.unit
def test_report_notes_flag_interim_v1_reference() -> None:
    report = compare_runs([ProjectRun("p1", v1_score=80.0, v2_score=80.0)])
    assert any("interim reference" in note for note in report.notes)
