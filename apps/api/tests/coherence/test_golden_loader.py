"""
Tolerant golden-corpus loader (ADR-009 §G) — ingests the Abengoa/Gemini JSON.

Refers to Suite ID: TS-UA-COH-CALIB-GOLDEN-LOADER-001.
"""
from __future__ import annotations

import json

import pytest

from src.coherence.calibration.golden_loader import load_golden

_GEMINI_SHAPED = json.dumps(
    [
        {
            "project_id": "espana_la_robla",
            "expert_score": 62,
            "per_category_scores": {"BUDGET": 40},
            "totals": {"contract_total": 1600000, "budget_total": 1200000, "currency": "EUR"},
            "findings": [
                {
                    "category": "budget",  # lower-case → normalized
                    "severity": "Critical",  # mixed-case → normalized
                    "is_true_positive": True,
                    "evidence": {"left_doc": "c.pdf", "right_doc": "b.xlsx"},
                },
                {"category": "NONSENSE", "severity": "high"},  # invalid category → dropped
            ],
        },
        {"project_id": "espana_biogas", "expert_score": None, "findings": []},
    ]
)


@pytest.mark.unit
def test_load_golden_parses_projects_and_normalizes_findings() -> None:
    projects = load_golden(_GEMINI_SHAPED)
    assert [p.project_id for p in projects] == ["espana_la_robla", "espana_biogas"]

    p0 = projects[0]
    assert p0.expert_score == pytest.approx(62.0)
    assert len(p0.findings) == 1  # the invalid-category finding was dropped
    assert p0.findings[0].category == "BUDGET"
    assert p0.findings[0].severity == "critical"
    assert p0.findings[0].is_true_positive is True
    assert p0.true_findings == p0.findings

    assert projects[1].expert_score is None
    assert projects[1].findings == ()


@pytest.mark.unit
def test_load_golden_tolerates_single_object_and_wrapper() -> None:
    single = load_golden(json.dumps({"project_id": "x", "expert_score": 80, "findings": []}))
    assert [p.project_id for p in single] == ["x"]

    wrapped = load_golden(
        json.dumps({"projects": [{"project_id": "y", "expert_score": 70, "findings": []}]})
    )
    assert [p.project_id for p in wrapped] == ["y"]


@pytest.mark.unit
def test_invalid_severity_defaults_to_medium() -> None:
    projects = load_golden(
        json.dumps(
            [{"project_id": "z", "findings": [{"category": "LEGAL", "severity": "catastrophic"}]}]
        )
    )
    assert projects[0].findings[0].severity == "medium"


@pytest.mark.unit
def test_non_list_payload_raises() -> None:
    with pytest.raises(ValueError, match="JSON array"):
        load_golden(json.dumps(42))
