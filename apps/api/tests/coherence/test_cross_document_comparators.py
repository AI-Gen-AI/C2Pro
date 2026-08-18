"""
Cross-document comparator invariants (ADR-023 Phase 1b).

Refers to Suite ID: TS-UD-COH-XDOC-COMPARATORS-001.
"""
from __future__ import annotations

import pytest

from src.coherence.cross_document import (
    RULE_CONTRACT_VS_BUDGET,
    CrossDocFinding,
    ProjectCrossDocInputs,
    budget_exceeds_contract,
    contract_vs_budget_total,
    risk_exceeds_contingency,
    run_numeric_comparators,
    schedule_overruns_deadline,
)


@pytest.mark.unit
def test_contract_vs_budget_material_discrepancy() -> None:
    """The €1.6M-vs-€1.2M case: a 25% gap is a material cross-document discrepancy."""
    inputs = ProjectCrossDocInputs(contract_total=1_600_000.0, budget_total=1_200_000.0)
    finding = contract_vs_budget_total(inputs)
    assert finding is not None
    assert finding.rule_id == RULE_CONTRACT_VS_BUDGET
    assert finding.category == "BUDGET"
    assert finding.delta == pytest.approx(400_000.0)
    assert finding.direction == "exceeds"
    assert finding.materiality_ratio == pytest.approx(0.25)
    assert finding.compared_values == {
        "contract_total": 1_600_000.0,
        "budget_total": 1_200_000.0,
    }


@pytest.mark.unit
def test_direction_below_when_budget_exceeds_contract() -> None:
    inputs = ProjectCrossDocInputs(contract_total=1_200_000.0, budget_total=1_600_000.0)
    finding = contract_vs_budget_total(inputs)
    assert finding is not None
    assert finding.direction == "below"
    assert finding.delta == pytest.approx(-400_000.0)


@pytest.mark.unit
def test_within_tolerance_is_not_flagged() -> None:
    """A sub-1% difference is rounding/noise, not a discrepancy."""
    inputs = ProjectCrossDocInputs(contract_total=1_000_000.0, budget_total=1_005_000.0)
    assert contract_vs_budget_total(inputs) is None


@pytest.mark.unit
def test_missing_value_yields_no_finding() -> None:
    assert contract_vs_budget_total(ProjectCrossDocInputs(contract_total=1_600_000.0)) is None
    assert contract_vs_budget_total(ProjectCrossDocInputs(budget_total=1_200_000.0)) is None
    assert contract_vs_budget_total(ProjectCrossDocInputs()) is None


@pytest.mark.unit
def test_both_zero_yields_no_finding() -> None:
    inputs = ProjectCrossDocInputs(contract_total=0.0, budget_total=0.0)
    assert contract_vs_budget_total(inputs) is None


@pytest.mark.unit
def test_run_numeric_comparators_returns_only_material() -> None:
    inputs = ProjectCrossDocInputs(
        contract_total=1_600_000.0,  # vs budget 1.2M → 25% (material, > 18% threshold)
        budget_total=1_200_000.0,
        wbs_total=900_000.0,  # vs budget 1.2M → 25% (material, > 18% threshold)
        bom_total=None,  # absent → skipped
    )
    findings = run_numeric_comparators(inputs)
    assert {f.rule_id for f in findings} == {"DET-CRS-CONBUD", "DET-CRS-WBSBUD"}
    assert all(isinstance(f, CrossDocFinding) for f in findings)


@pytest.mark.unit
def test_run_numeric_comparators_all_aligned_is_empty() -> None:
    inputs = ProjectCrossDocInputs(
        contract_total=1_000_000.0,
        budget_total=1_000_000.0,
        wbs_total=1_000_000.0,
        bom_total=1_000_000.0,
    )
    assert run_numeric_comparators(inputs) == []


@pytest.mark.unit
def test_finding_flows_into_conflict_ledger_as_critical() -> None:
    """End-to-end: a 25% contract↔budget gap becomes a critical BUDGET hard conflict."""
    from src.coherence.cross_document import to_finding_signal
    from src.coherence.services.v2.conflict_service import (
        ConflictService,
        build_conflict_candidates,
    )
    from src.coherence.services.v2.evidence_service import EvidenceBundle

    finding = contract_vs_budget_total(
        ProjectCrossDocInputs(contract_total=1_600_000.0, budget_total=1_200_000.0)
    )
    assert finding is not None
    signal = to_finding_signal(finding)

    candidates = build_conflict_candidates([signal])
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule_id == "DET-CRS-CONBUD"
    assert candidate.category == "BUDGET"
    assert candidate.compared_values == {
        "contract_total": 1_600_000.0,
        "budget_total": 1_200_000.0,
    }
    assert candidate.delta == pytest.approx(400_000.0)

    report = ConflictService().detect(
        "BUDGET", EvidenceBundle(3, 0.9, 0.9, 0.9, [], []), candidates
    )
    assert report.hard_conflict is True
    assert report.severity == "critical"  # 25% > CRITICAL_MISMATCH_RATIO (0.20)


@pytest.mark.unit
def test_negative_margin_flags_budget_above_contract() -> None:
    """MONFORTE-like: budget 18.3M > contract 15.1M — a 17.6% overrun below the symmetric
    18% threshold, but a budget exceeding the contract is always a negative-margin incoherence."""
    inputs = ProjectCrossDocInputs(contract_total=15_105_733.99, budget_total=18_324_935.31)
    finding = budget_exceeds_contract(inputs)
    assert finding is not None
    assert finding.rule_id == "DET-CRS-NEGMARGIN"
    assert finding.category == "BUDGET"
    assert finding.direction == "exceeds"
    # The symmetric comparator misses it (17.6% < 18%); the corpus runner catches it.
    assert contract_vs_budget_total(inputs) is None
    assert any(f.rule_id == "DET-CRS-NEGMARGIN" for f in run_numeric_comparators(inputs))


@pytest.mark.unit
def test_negative_margin_silent_when_budget_below_contract() -> None:
    """A budget below the contract is a normal margin, not a negative-margin incoherence."""
    inputs = ProjectCrossDocInputs(contract_total=1_600_000.0, budget_total=1_200_000.0)
    assert budget_exceeds_contract(inputs) is None


@pytest.mark.unit
def test_risk_exceeds_contingency_flags_underprovisioned_budget() -> None:
    """RIYADH-like: a $300M identified risk exceeds a $50M contingency fund."""
    inputs = ProjectCrossDocInputs(contingency=50_000_000.0, max_risk_exposure=300_000_000.0)
    finding = risk_exceeds_contingency(inputs)
    assert finding is not None
    assert finding.rule_id == "DET-CRS-RISKCONT"
    assert finding.category == "BUDGET"
    assert finding.direction == "exceeds"
    assert any(f.rule_id == "DET-CRS-RISKCONT" for f in run_numeric_comparators(inputs))


@pytest.mark.unit
def test_risk_within_contingency_is_silent() -> None:
    covered = ProjectCrossDocInputs(contingency=50_000_000.0, max_risk_exposure=40_000_000.0)
    assert risk_exceeds_contingency(covered) is None
    # missing either side → silent (no false positive)
    assert risk_exceeds_contingency(ProjectCrossDocInputs(contingency=50_000_000.0)) is None
    assert risk_exceeds_contingency(ProjectCrossDocInputs(max_risk_exposure=300.0)) is None


@pytest.mark.unit
def test_schedule_overruns_deadline_flags_time_incoherence() -> None:
    """Schedule ending after the contract deadline is a TIME incoherence."""
    inputs = ProjectCrossDocInputs(contract_deadline="2026-07-01", schedule_end="2026-07-15")
    finding = schedule_overruns_deadline(inputs)
    assert finding is not None
    assert finding.rule_id == "DET-CRS-SCHDEAD"
    assert finding.category == "TIME"
    assert finding.delta == pytest.approx(14.0)  # 14 days overrun
    assert any(f.rule_id == "DET-CRS-SCHDEAD" for f in run_numeric_comparators(inputs))


@pytest.mark.unit
def test_schedule_within_deadline_is_silent() -> None:
    on_time = ProjectCrossDocInputs(contract_deadline="2026-07-15", schedule_end="2026-07-01")
    assert schedule_overruns_deadline(on_time) is None
    assert schedule_overruns_deadline(ProjectCrossDocInputs(schedule_end="2026-07-15")) is None
    assert schedule_overruns_deadline(ProjectCrossDocInputs(contract_deadline="bad")) is None
