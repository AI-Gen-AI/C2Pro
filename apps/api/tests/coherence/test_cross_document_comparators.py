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
    contract_vs_budget_total,
    run_numeric_comparators,
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
        contract_total=1_600_000.0,  # vs budget 1.2M → 25% (material)
        budget_total=1_200_000.0,
        wbs_total=1_000_000.0,  # vs budget 1.2M → 16.7% (material)
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
