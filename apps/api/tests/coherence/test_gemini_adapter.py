"""
Gemini golden-schema adapter (ADR-009 §G).

Refers to Suite ID: TS-UA-COH-CALIB-GEMINI-ADAPTER-001.
"""
from __future__ import annotations

import pytest

from src.coherence.calibration.gemini_adapter import (
    alert_category,
    gemini_budget_inputs,
    gemini_expected_categories,
    gemini_to_golden_project,
)

# Shaped after the real AL-Zour golden (KWD, JV totals, LEG + BUDGET alerts).
_ALZOUR = {
    "project_metadata": {"id": "P-KW-01"},
    "input_documents": {
        "contract_text": "Total: 580,000,000.00 KWD. Exempt from delays.",
        "risk_analysis_text": "AR: delay penalties 100,000 KWD/day apply.",
        "budget_summary": {"total_value_kwd": 580000000.0, "budget_total_kwd": 530000000.0},
    },
    "expected_output": {
        "coherence_alerts": [
            {"rule_id": "LEG-KWT-01", "severity": "critical", "description": "exempt vs penalty"},
            {"rule_id": "BUD-KWT-02", "severity": "high", "description": "580M vs 530M"},
        ]
    },
}


@pytest.mark.unit
def test_alert_category_maps_prefixes() -> None:
    assert alert_category("LEG-KWT-01") == "LEGAL"
    assert alert_category("SCH-CTR-01") == "TIME"
    assert alert_category("BUD-01") == "BUDGET"
    assert alert_category("LOC-MISMATCH-01") == "SCOPE"
    assert alert_category("ZZZ-01") is None


@pytest.mark.unit
def test_gemini_budget_inputs_extracts_multicurrency_totals() -> None:
    inputs = gemini_budget_inputs(_ALZOUR)
    assert inputs.contract_total == pytest.approx(580000000.0)
    assert inputs.budget_total == pytest.approx(530000000.0)


@pytest.mark.unit
def test_gemini_budget_inputs_falls_back_to_jv_sub_budget() -> None:
    project = {"input_documents": {"budget_summary": {
        "total_value_eur": 47136575.38, "inabensa_sub_budget_total_eur": 22194629.66}}}
    inputs = gemini_budget_inputs(project)
    assert inputs.contract_total == pytest.approx(47136575.38)
    assert inputs.budget_total == pytest.approx(22194629.66)  # JV partner share


@pytest.mark.unit
def test_gemini_expected_categories() -> None:
    assert gemini_expected_categories(_ALZOUR) == frozenset({"LEGAL", "BUDGET"})


@pytest.mark.unit
def test_gemini_to_golden_project() -> None:
    golden = gemini_to_golden_project(_ALZOUR)
    assert golden.project_id == "P-KW-01"
    assert {f.category for f in golden.findings} == {"LEGAL", "BUDGET"}
    assert {f.severity for f in golden.findings} == {"critical", "high"}


@pytest.mark.unit
def test_missing_budget_summary_is_safe() -> None:
    inputs = gemini_budget_inputs({"input_documents": {}})
    assert inputs.contract_total is None
    assert inputs.budget_total is None
    assert gemini_expected_categories({}) == frozenset()


@pytest.mark.unit
def test_gemini_extracts_contingency_and_risk_exposure() -> None:
    project = {
        "input_documents": {
            "risk_analysis_text": (
                "Risk Analysis identifies a tunneling cost overrun of $300,000,000.00 "
                "which exceeds the contingency fund."
            ),
            "budget_summary": {"total_value_usd": 1_250_000_000.0, "contingency_usd": 50_000_000.0},
        }
    }
    inputs = gemini_budget_inputs(project)
    assert inputs.contingency == pytest.approx(50_000_000.0)
    assert inputs.max_risk_exposure == pytest.approx(300_000_000.0)


@pytest.mark.unit
def test_gemini_extracts_schedule_and_spanish_deadline() -> None:
    project = {
        "input_documents": {
            "contract_text": "El Contratista se compromete a la entrega a más tardar el 1 de Julio de 2026.",
            "schedule_summary": {"project_end_date": "2026-07-15"},
        }
    }
    inputs = gemini_budget_inputs(project)
    assert inputs.contract_deadline == "2026-07-01"  # parsed from Spanish text
    assert inputs.schedule_end == "2026-07-15"
