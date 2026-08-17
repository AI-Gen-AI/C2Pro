"""
Calibration gate — engine vs expert golden (ADR-009 §G).

Refers to Suite ID: TS-UA-COH-CALIB-GATE-001.
"""
from __future__ import annotations

import pytest

from src.coherence.calibration.gate import EngineRun, evaluate_against_golden
from src.coherence.calibration.golden import GoldenFinding, GoldenProject


@pytest.mark.unit
def test_engine_matching_expert_scores_perfect() -> None:
    golden = [GoldenProject("p1", 78.0, (GoldenFinding("BUDGET", "critical", True),))]
    runs = [EngineRun("p1", 78.0, frozenset({"BUDGET"}))]
    report = evaluate_against_golden(runs, golden, detectable_categories=("BUDGET",))
    assert report.score_mae == pytest.approx(0.0)
    assert report.critical_findings.precision == pytest.approx(1.0)
    assert report.critical_findings.recall == pytest.approx(1.0)
    assert report.project_count == 1


@pytest.mark.unit
def test_engine_missing_expert_finding_lowers_recall() -> None:
    golden = [
        GoldenProject(
            "p1",
            60.0,
            (GoldenFinding("BUDGET", "critical", True), GoldenFinding("LEGAL", "high", True)),
        )
    ]
    runs = [EngineRun("p1", 62.0, frozenset({"BUDGET"}))]  # engine missed LEGAL
    report = evaluate_against_golden(runs, golden, detectable_categories=("BUDGET", "LEGAL"))
    assert report.critical_findings.tp == 1
    assert report.critical_findings.fn == 1  # LEGAL expert finding not flagged
    assert report.score_mae == pytest.approx(2.0)


@pytest.mark.unit
def test_scoping_to_detectable_excludes_qualitative_gap() -> None:
    # Expert flags LEGAL (qualitative, engine can't detect); scoping to BUDGET keeps recall honest.
    golden = [
        GoldenProject(
            "p1",
            60.0,
            (GoldenFinding("BUDGET", "critical", True), GoldenFinding("LEGAL", "medium", True)),
        )
    ]
    runs = [EngineRun("p1", 60.0, frozenset({"BUDGET"}))]
    report = evaluate_against_golden(runs, golden, detectable_categories=("BUDGET",))
    assert report.critical_findings.recall == pytest.approx(1.0)


@pytest.mark.unit
def test_engine_false_positive_vs_expert() -> None:
    golden = [GoldenProject("p1", 90.0, ())]  # expert: no real findings
    runs = [EngineRun("p1", 60.0, frozenset({"BUDGET"}))]  # engine raised BUDGET
    report = evaluate_against_golden(runs, golden, detectable_categories=("BUDGET",))
    assert report.critical_findings.fp == 1
    assert report.critical_findings.precision == pytest.approx(0.0)


@pytest.mark.unit
def test_unmatched_runs_and_golden_are_ignored() -> None:
    golden = [GoldenProject("p1", 80.0, ())]
    runs = [EngineRun("other", 50.0, frozenset()), EngineRun("p1", 80.0, frozenset())]
    report = evaluate_against_golden(runs, golden)
    assert report.project_count == 1
    assert report.score_mae == pytest.approx(0.0)
