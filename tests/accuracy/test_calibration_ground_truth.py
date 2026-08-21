"""
Calibration Ground Truth Verification (TS-UA-COH-CALIB-GROUND-TRUTH-001)

This module contains test cases to verify that the three selected Spain-batch
calibration projects (LAV La Robla, Planta Biogás Campillos, and LAV Monforte-Murcia)
have been updated with the extracted ground truth contract, budget, and schedule parameters.
"""

import json
from pathlib import Path
import pytest

GOLDEN_DATASET_PATH = Path(__file__).parent.parent / "golden" / "real"


def _load_project(filename: str, country: str = "españa") -> dict:
    path = GOLDEN_DATASET_PATH / country / filename
    assert path.exists(), f"Expected golden file {filename} does not exist at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_la_robla_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for LAV La Robla (espana_la_robla).
    - Extracted contract total: 47,136,575.38 EUR (sin IVA)
    - Extracted Inabensa sub-budget total: 22,194,629.66 EUR
    - Geographical name discrepancy exists: folder name (La Roda) vs contract (La Robla)
    """
    project = _load_project("project_LA_ROBLA.json")
    
    # Verify contract totals
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_value_eur") == 47136575.38
    assert budget_summary.get("inabensa_sub_budget_total_eur") == 22194629.66
    
    # Verify geographical mismatch alert is defined
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    loc_alerts = [a for f in alerts if (a := f).get("rule_id") == "LOC-MISMATCH-01"]
    assert len(loc_alerts) >= 1
    
    alert = loc_alerts[0]
    assert alert.get("severity") == "critical"
    assert "La Roda" in str(alert.get("description"))
    assert "La Robla" in str(alert.get("description"))


def test_campillos_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for Planta Biogás Campillos (espana_campillos).
    - Extracted contract total investment estimate: 3,717,117.00 EUR
    - Extracted budget total: 2,514,926.11 EUR
    - Critical legal dependencies on Power Purchase Agreement (PPA)
    - Strict financial IRR targets: 9% project, 22% shareholder
    """
    project = _load_project("project_CAMPILLOS.json")
    
    # Verify investment and budget values
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_investment_eur") == 3717117
    assert budget_summary.get("budget_total_eur") == 2514926.11
    
    # Verify IRR targets
    assert budget_summary.get("target_irr_project_pct") == 9.0
    assert budget_summary.get("target_irr_shareholder_pct") == 22.0
    
    # Verify legal/financial alerts exist
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    fin_alerts = [a for f in alerts if (a := f).get("rule_id") == "RISK-FIN-01"]
    op_alerts = [a for f in alerts if (a := f).get("rule_id") == "RISK-OP-01"]
    
    assert len(fin_alerts) >= 1
    assert len(op_alerts) >= 1
    
    assert fin_alerts[0].get("severity") == "critical"
    assert "TIR" in str(fin_alerts[0].get("description")) or "IRR" in str(fin_alerts[0].get("description"))
    assert op_alerts[0].get("severity") == "warning"
    assert "PPA" in str(op_alerts[0].get("description"))


def test_monforte_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for LAV Monforte-Murcia (espana_monforte).
    - Extracted contract/adjudication total: 15,105,733.99 EUR
    - Extracted internal cost estimate: 18,324,935.31 EUR
    - Extracted budget base (tender Licitación): 26,316,667.92 EUR
    - Schedule duration discrepancy: Tender states 17 months, internal specifies 24 months
    """
    project = _load_project("project_MONFORTE.json")
    
    # Verify budget and cost values
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("tender_budget_pem") == 26316667.92
    assert budget_summary.get("internal_cost_estimate") == 18324935.31
    assert budget_summary.get("revenue_target") == 15105733.99
    
    # Verify schedule durations
    schedule_summary = project.get("input_documents", {}).get("schedule_summary", {})
    assert schedule_summary.get("tender_duration_months") == 17
    assert schedule_summary.get("internal_duration_months") == 24
    
    # Verify alerts exist
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    fin_alerts = [a for f in alerts if (a := f).get("rule_id") == "FIN-MON-01"]
    sch_alerts = [a for f in alerts if (a := f).get("rule_id") == "SCH-MON-01"]
    
    assert len(fin_alerts) >= 1
    assert len(sch_alerts) >= 1
    
    assert fin_alerts[0].get("severity") == "critical"
    assert sch_alerts[0].get("severity") == "high"
    assert "17" in str(sch_alerts[0].get("description"))
    assert "24" in str(sch_alerts[0].get("description"))


def test_mexico_queretaro_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for LAV México - Querétaro (mexico_queretaro).
    - Extracted contract total: 50,820,000,000.00 MXN (sin IVA)
    - Extracted budget total: 42,150,000,000.00 MXN
    - Location name discrepancy exists: folder name (Celaya) vs contract (Querétaro)
    """
    project = _load_project("project_QUERETARO.json", country="mexico")
    
    # Verify contract totals
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_value_mxn") == 50820000000.00
    assert budget_summary.get("budget_total_mxn") == 42150000000.00
    
    # Verify geographical mismatch alert is defined
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    loc_alerts = [a for f in alerts if (a := f).get("rule_id") == "LOC-MISMATCH-01"]
    assert len(loc_alerts) >= 1
    
    alert = loc_alerts[0]
    assert alert.get("severity") == "critical"
    assert "Celaya" in str(alert.get("description"))
    assert "Querétaro" in str(alert.get("description"))


def test_brasil_rio_sp_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for TAV Rio - São Paulo (brasil_tav_rio_sp).
    - Extracted contract total: 34,600,000,000.00 BRL (sin IVA)
    - Extracted budget total: 31,200,000,000.00 BRL
    - Location name discrepancy exists: folder name (Campinas) vs contract (São Paulo)
    """
    project = _load_project("project_RIO_SP.json", country="brasil")
    
    # Verify contract totals
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_value_brl") == 34600000000.00
    assert budget_summary.get("budget_total_brl") == 31200000000.00
    
    # Verify geographical mismatch alert is defined
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    loc_alerts = [a for f in alerts if (a := f).get("rule_id") == "LOC-MISMATCH-01"]
    assert len(loc_alerts) >= 1
    
    alert = loc_alerts[0]
    assert alert.get("severity") == "critical"
    assert "Campinas" in str(alert.get("description"))
    assert "São Paulo" in str(alert.get("description"))


def test_usa_texas_grid_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for Texas Clean Energy Grid (usa_texas_grid).
    - Extracted contract total: 245,000,000.00 USD
    - Extracted budget total: 220,000,000.00 USD
    - Risk Analysis (AR) schedule mismatch alert: 36 months contract vs 48 months risk
    """
    project = _load_project("project_TEXAS_GRID.json", country="usa")
    
    # Verify contract totals
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_value_usd") == 245000000.00
    assert budget_summary.get("budget_total_usd") == 220000000.00
    
    # Verify schedule mismatch alert (Contract vs Risk Analysis (AR)) is defined
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    sch_alerts = [a for f in alerts if (a := f).get("rule_id") == "SCH-USA-01"]
    assert len(sch_alerts) >= 1
    
    alert = sch_alerts[0]
    assert alert.get("severity") == "critical"
    assert "36" in str(alert.get("description"))
    assert "48" in str(alert.get("description"))


def test_saudi_riyadh_metro_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for Riyadh Metro Line 3 (saudi_riyadh_metro).
    - Extracted contract total: 1,250,000,000.00 USD
    - Extracted budget total: 1,200,000,000.00 USD
    - Contingency budget: 50,000,000.00 USD
    - Risk Analysis (AR) budget overrun risk: $300,000,000.00 civil tunneling cost exceeds $50M contingency
    """
    project = _load_project("project_RIYADH_METRO.json", country="saudi")
    
    # Verify contract totals
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_value_usd") == 1250000000.00
    assert budget_summary.get("contingency_usd") == 50000000.00
    
    # Verify budget mismatch alert (Contingency vs Risk Analysis (AR)) is defined
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    bud_alerts = [a for f in alerts if (a := f).get("rule_id") == "BUD-SAU-01"]
    assert len(bud_alerts) >= 1
    
    alert = bud_alerts[0]
    assert alert.get("severity") == "critical"
    assert "300,000,000" in str(alert.get("description"))
    assert "50,000,000" in str(alert.get("description"))


def test_kuwait_al_zour_ground_truth_calibration():
    """
    Verifies the ground truth extraction parameters for Al-Zour Refinery Expansion (kuwait_al_zour).
    - Extracted contract total: 580,000,000.00 KWD
    - Extracted budget total: 530,000,000.00 KWD
    - Risk Analysis (AR) legal penalty risk: contract exemption vs 100,000 KWD/day municipal delay penalty
    """
    project = _load_project("project_AL_ZOUR.json", country="kuwait")
    
    # Verify contract totals
    budget_summary = project.get("input_documents", {}).get("budget_summary", {})
    assert budget_summary.get("total_value_kwd") == 580000000.00
    assert budget_summary.get("budget_total_kwd") == 530000000.00
    
    # Verify legal penalty alert (Exemption vs Municipal Law Risk Analysis (AR)) is defined
    alerts = project.get("expected_output", {}).get("coherence_alerts", [])
    leg_alerts = [a for f in alerts if (a := f).get("rule_id") == "LEG-KWT-01"]
    assert len(leg_alerts) >= 1
    
    alert = leg_alerts[0]
    assert alert.get("severity") == "critical"
    assert "exempt" in str(alert.get("description"))
    assert "100,000" in str(alert.get("description"))


