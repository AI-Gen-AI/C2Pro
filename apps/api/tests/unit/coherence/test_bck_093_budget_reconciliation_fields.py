"""TS-BCK-093: budget reconciliation fields exposed in categories_v2.BUDGET.

Verifies that the calculate_v2_from_signals scoring path populates
BudgetReconciliation with currency and source_rule_ids so the UI
no longer parses generic detected_conflicts/metadata strings.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import BudgetReconciliation
from src.coherence.models import FindingSignal
from src.coherence.scoring import calculate_v2_from_signals
from src.coherence.services.v2.evidence_service import EvidenceBundle


def _budget_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        count=1,
        evidence_coverage=0.8,
        evidence_freshness=1.0,
        avg_technical_reliability=1.0,
        missing_required=[],
        references=["budget-clause-1"],
    )


def _empty_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        count=0,
        evidence_coverage=0.0,
        evidence_freshness=0.0,
        avg_technical_reliability=0.0,
        missing_required=[],
        references=[],
    )


def _applicability_all_applicable() -> dict[str, tuple[bool, str | None]]:
    from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
    return dict.fromkeys(MIN_EVIDENCE_BY_CATEGORY, (True, None))


def test_bck093_source_rule_ids_populated_for_det_bud_sum() -> None:
    """DET-BUD-SUM signal → BudgetReconciliation.source_rule_ids contains rule id."""
    project_id = uuid4()
    signals = [
        FindingSignal(
            rule_id="DET-BUD-SUM",
            clause_id="clause-budget-1",
            source="deterministic",
            impact_score=0.6,
            category="BUDGET",
            raw_data={
                "items_sum": 636_044_805.0,
                "contract_total": 628_624_801.0,
                "deviation_pct": 1.18,
                "direction": "exceeds",
            },
        )
    ]
    from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
    evidence = {cat: _empty_bundle() for cat in MIN_EVIDENCE_BY_CATEGORY}
    evidence["BUDGET"] = _budget_bundle()

    payload = calculate_v2_from_signals(
        signals=signals,
        evidence_bundles=evidence,
        applicability_map=_applicability_all_applicable(),
        project_id=project_id,
    )

    budget_cat = next(c for c in payload.categories if c.category == "BUDGET")
    assert budget_cat.budget_reconciliation is not None
    recon = budget_cat.budget_reconciliation
    assert recon.items_sum == pytest.approx(636_044_805.0)
    assert recon.contract_total == pytest.approx(628_624_801.0)
    assert recon.deviation_pct == pytest.approx(1.18)
    assert recon.direction == "exceeds"
    assert "DET-BUD-SUM" in recon.source_rule_ids


def test_bck093_currency_exposed_when_present_in_raw_data() -> None:
    """currency in raw_data flows through to BudgetReconciliation.currency."""
    project_id = uuid4()
    signals = [
        FindingSignal(
            rule_id="DET-BUD-INTERNAL",
            clause_id="clause-budget-2",
            source="deterministic",
            impact_score=0.5,
            category="BUDGET",
            raw_data={
                "items_sum": 500_000.0,
                "stated_total": 540_000.0,
                "deviation_pct": 7.41,
                "direction": "below",
                "currency": "USD",
            },
        )
    ]
    from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
    evidence = {cat: _empty_bundle() for cat in MIN_EVIDENCE_BY_CATEGORY}
    evidence["BUDGET"] = _budget_bundle()

    payload = calculate_v2_from_signals(
        signals=signals,
        evidence_bundles=evidence,
        applicability_map=_applicability_all_applicable(),
        project_id=project_id,
    )

    budget_cat = next(c for c in payload.categories if c.category == "BUDGET")
    assert budget_cat.budget_reconciliation is not None
    recon = budget_cat.budget_reconciliation
    assert recon.currency == "USD"
    assert recon.stated_total == pytest.approx(540_000.0)
    assert "DET-BUD-INTERNAL" in recon.source_rule_ids


def test_bck093_both_rules_merge_into_single_reconciliation() -> None:
    """DET-BUD-SUM + DET-BUD-INTERNAL merged: stated_total and contract_total both present."""
    project_id = uuid4()
    signals = [
        FindingSignal(
            rule_id="DET-BUD-SUM",
            clause_id="clause-budget-3",
            source="deterministic",
            impact_score=0.6,
            category="BUDGET",
            raw_data={
                "items_sum": 636_044_805.0,
                "contract_total": 628_624_801.0,
                "deviation_pct": 1.18,
                "direction": "exceeds",
                "currency": "INR",
            },
        ),
        FindingSignal(
            rule_id="DET-BUD-INTERNAL",
            clause_id="clause-budget-3",
            source="deterministic",
            impact_score=0.5,
            category="BUDGET",
            raw_data={
                "items_sum": 636_044_805.0,
                "stated_total": 654_144_805.0,
                "deviation_pct": 2.77,
                "direction": "below",
                "currency": "INR",
            },
        ),
    ]
    from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
    evidence = {cat: _empty_bundle() for cat in MIN_EVIDENCE_BY_CATEGORY}
    evidence["BUDGET"] = _budget_bundle()

    payload = calculate_v2_from_signals(
        signals=signals,
        evidence_bundles=evidence,
        applicability_map=_applicability_all_applicable(),
        project_id=project_id,
    )

    budget_cat = next(c for c in payload.categories if c.category == "BUDGET")
    assert budget_cat.budget_reconciliation is not None
    recon = budget_cat.budget_reconciliation
    assert recon.contract_total == pytest.approx(628_624_801.0)
    assert recon.stated_total == pytest.approx(654_144_805.0)
    assert recon.currency == "INR"
    assert "DET-BUD-SUM" in recon.source_rule_ids
    assert "DET-BUD-INTERNAL" in recon.source_rule_ids


def test_bck093_non_budget_category_has_no_budget_reconciliation() -> None:
    """Non-BUDGET categories keep budget_reconciliation as None."""
    project_id = uuid4()
    from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
    evidence = {cat: _empty_bundle() for cat in MIN_EVIDENCE_BY_CATEGORY}

    payload = calculate_v2_from_signals(
        signals=[],
        evidence_bundles=evidence,
        applicability_map=_applicability_all_applicable(),
        project_id=project_id,
    )

    for cat in payload.categories:
        if cat.category != "BUDGET":
            assert cat.budget_reconciliation is None


def test_bck093_budget_reconciliation_model_has_required_fields() -> None:
    """BudgetReconciliation DTO exposes currency and source_rule_ids (BCK-093 spec fields)."""
    recon = BudgetReconciliation(
        items_sum=100_000.0,
        stated_total=110_000.0,
        contract_total=95_000.0,
        deviation_pct=5.26,
        direction="exceeds",
        currency="EUR",
        source_rule_ids=["DET-BUD-SUM", "DET-BUD-INTERNAL"],
    )
    assert recon.currency == "EUR"
    assert recon.source_rule_ids == ["DET-BUD-SUM", "DET-BUD-INTERNAL"]
    serialized = recon.model_dump(mode="json")
    assert serialized["currency"] == "EUR"
    assert "DET-BUD-SUM" in serialized["source_rule_ids"]


def test_bck093_currency_none_by_default() -> None:
    """currency field defaults to None when not in raw_data."""
    recon = BudgetReconciliation(
        items_sum=50_000.0,
        deviation_pct=3.0,
        direction="below",
    )
    assert recon.currency is None
    assert recon.source_rule_ids == []
