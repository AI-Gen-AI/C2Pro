"""
Scorer-direct gate invariants (ADR-009 §G.1, criteria 3-4).

Refers to Suite ID: TS-UA-COH-CALIB-SCORER-GATE-001.
"""
from __future__ import annotations

import pytest

from src.coherence.calibration.scorer_gate import (
    expert_score,
    golden_category_conflicts,
    score_golden_project,
    v1_score_golden,
)

_CLEAN = {"expected_output": {"expert_score": 100, "coherence_alerts": []}}
_CRITICAL_BUDGET = {
    "expected_output": {
        "expert_score": 85,
        "coherence_alerts": [
            {"rule_id": "BUD-01", "severity": "critical", "category": "BUDGET",
             "evidence_verified": True},
        ],
    }
}


@pytest.mark.unit
def test_clean_project_scores_near_100() -> None:
    assert score_golden_project(_CLEAN) == pytest.approx(100.0)
    assert golden_category_conflicts(_CLEAN) == {}


@pytest.mark.unit
def test_critical_finding_depresses_but_never_zero() -> None:
    score = score_golden_project(_CRITICAL_BUDGET)
    assert score is not None
    assert 5.0 <= score < 100.0  # conflict != 0 (ADR-009 §A/§B), yet materially depressed
    conflicts = golden_category_conflicts(_CRITICAL_BUDGET)
    assert conflicts["BUDGET"].severity == "critical"
    assert conflicts["BUDGET"].certainty == 1.0  # golden is ground truth


@pytest.mark.unit
def test_unverified_alert_is_excluded_from_ground_truth() -> None:
    project = {
        "expected_output": {
            "coherence_alerts": [
                {"rule_id": "BUD-01", "severity": "critical", "category": "BUDGET",
                 "evidence_verified": False},
            ]
        }
    }
    assert golden_category_conflicts(project) == {}


@pytest.mark.unit
def test_worst_severity_per_category_wins() -> None:
    project = {
        "expected_output": {
            "coherence_alerts": [
                {"rule_id": "BUD-01", "severity": "medium", "category": "BUDGET",
                 "evidence_verified": True},
                {"rule_id": "BUD-02", "severity": "critical", "category": "BUDGET",
                 "evidence_verified": True},
            ]
        }
    }
    assert golden_category_conflicts(project)["BUDGET"].severity == "critical"


@pytest.mark.unit
def test_expert_score_reads_ground_truth() -> None:
    assert expert_score(_CRITICAL_BUDGET) == pytest.approx(85.0)
    assert expert_score({"expected_output": {}}) is None
    assert expert_score({}) is None


@pytest.mark.unit
def test_v1_baseline_over_penalizes_relative_to_canonical() -> None:
    """Criterion-5 baseline: v1's flat penalty (-35 for a critical -> 65) lands further from
    the expert (85) than the calibrated canonical scorer, on the SAME finding."""
    v1 = v1_score_golden(_CRITICAL_BUDGET)
    canonical = score_golden_project(_CRITICAL_BUDGET)
    assert v1_score_golden(_CLEAN) == pytest.approx(100.0)
    assert 0.0 <= v1 <= 100.0
    assert v1 < canonical  # v1 over-penalizes a lone critical vs the expert-calibrated canonical
