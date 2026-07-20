# tests/coherence/test_deterministic_evaluators.py
"""
Unit tests for all 27 deterministic evaluators (v0.3).

Covers:
- BUDGET (6): BudgetOverrun, BudgetContingency, BudgetLineItem, BudgetSumMismatch, RetentionRate, AdvancePayment
- TIME (5): ScheduleStatus, DeadlineOverdue, MilestoneGap, PredecessorOverlap, ScheduleDuration
- LEGAL (6): ContractReviewOverdue, PenaltyCap, NoticePeriod, WarrantyPeriod, PaymentTerm, InsuranceExpiry
- TECHNICAL (3): BomLeadTime, SpecReference, BomBudgetLink
- QUALITY (2): QualityStandard, InspectionFrequency
- SCOPE (2): MissingRequiredFields, ScopeDeliverables
- CROSS (3): BudgetVsContractTotal, ScheduleVsBomDelivery, ScopeVsBudgetCoverage

Location: apps/api/tests/coherence/test_deterministic_evaluators.py
"""

from datetime import date, datetime, timedelta

import pytest

from src.coherence.models import Clause, FindingSignal
from src.coherence.rules_engine.config import EvaluatorConfig
from src.coherence.rules_engine.deterministic import (
    AdvancePaymentEvaluator,
    BomBudgetLinkEvaluator,
    # TECHNICAL
    BomLeadTimeEvaluator,
    BudgetContingencyEvaluator,
    BudgetInternalConsistencyEvaluator,
    BudgetLineItemEvaluator,
    # BUDGET
    BudgetOverrunEvaluator,
    BudgetSumMismatchEvaluator,
    # CROSS
    BudgetVsContractTotalEvaluator,
    # LEGAL
    ContractReviewOverdueEvaluator,
    DeadlineOverdueEvaluator,
    InspectionFrequencyEvaluator,
    InsuranceExpiryEvaluator,
    MilestoneGapEvaluator,
    # SCOPE
    MissingRequiredFieldsEvaluator,
    NoticePeriodEvaluator,
    PaymentTermEvaluator,
    PenaltyCapEvaluator,
    PredecessorOverlapEvaluator,
    # QUALITY
    QualityStandardEvaluator,
    RetentionRateEvaluator,
    ScheduleDurationEvaluator,
    # TIME
    ScheduleStatusEvaluator,
    ScheduleVsBomDeliveryEvaluator,
    ScopeDeliverablesEvaluator,
    ScopeVsBudgetCoverageEvaluator,
    SpecReferenceEvaluator,
    WarrantyPeriodEvaluator,
    _num,
    _parse_date,
    # Helpers and registry
    get_all_deterministic_evaluators,
)

# ===========================================
# HELPER FUNCTION TESTS
# ===========================================


class TestHelperFunctions:
    """Tests for the _num and _parse_date helper functions."""

    @pytest.mark.parametrize("val,expected", [
        (0, True),
        (1, True),
        (-1, True),
        (1.5, True),
        (-3.14, True),
        (0.0, True),
        ("1", False),
        ("1.5", False),
        (None, False),
        (True, False),  # bool is excluded
        (False, False),
        ([], False),
        ({}, False),
    ])
    def test_num_function(self, val, expected: bool):
        """Test _num helper for numeric type detection."""
        assert _num(val) == expected

    @pytest.mark.parametrize("val,expected", [
        (date(2025, 6, 15), date(2025, 6, 15)),
        (datetime(2025, 6, 15, 10, 30), date(2025, 6, 15)),
        ("2025-06-15", date(2025, 6, 15)),
        ("2025-06-15T10:30:00", date(2025, 6, 15)),
        ("2025-06-15T10:30:00Z", date(2025, 6, 15)),
        ("15/06/2025", date(2025, 6, 15)),  # DD/MM/YYYY
        ("06/15/2025", date(2025, 6, 15)),  # MM/DD/YYYY
        ("", None),
        (None, None),
        ("not-a-date", None),
        (123, None),
    ])
    def test_parse_date_function(self, val, expected):
        """Test _parse_date helper for date parsing."""
        assert _parse_date(val) == expected


# ===========================================
# BUDGET EVALUATOR TESTS
# ===========================================


class TestBudgetOverrunEvaluator:
    """Tests for DET-BUD-OVERRUN evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BudgetOverrunEvaluator()

    def test_metadata(self, evaluator):
        """Test evaluator metadata."""
        assert evaluator.rule_id == "DET-BUD-OVERRUN"
        assert evaluator.category == "BUDGET"

    def test_no_overrun(self, evaluator):
        """Test no finding when within budget."""
        clause = Clause(
            id="C001",
            text="Budget section",
            data={"current": 95000, "planned": 100000}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_warning_threshold_overrun(self, evaluator):
        """Test finding at warning threshold (5%)."""
        clause = Clause(
            id="C001",
            text="Budget section",
            data={"current": 106000, "planned": 100000}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.rule_id == "DET-BUD-OVERRUN"
        # 6% overrun normalized to 25% critical threshold → ~0.46 impact
        assert 0.40 <= signal.impact_score <= 0.55

    def test_critical_overrun(self, evaluator):
        """Test high impact at critical threshold (25%)."""
        clause = Clause(
            id="C001",
            text="Budget section",
            data={"current": 125000, "planned": 100000}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.impact_score >= 0.70

    def test_extreme_overrun(self, evaluator):
        """Test impact capped at 0.95 for extreme overruns."""
        clause = Clause(
            id="C001",
            text="Budget section",
            data={"current": 250000, "planned": 100000}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.impact_score <= 0.95

    def test_missing_data(self, evaluator):
        """Test no finding with missing data."""
        clause = Clause(id="C001", text="Budget", data={"current": 100000})
        assert evaluator.evaluate_v3(clause) is None

    def test_zero_planned(self, evaluator):
        """Test no finding with zero planned budget."""
        clause = Clause(
            id="C001",
            text="Budget",
            data={"current": 100000, "planned": 0}
        )
        assert evaluator.evaluate_v3(clause) is None


class TestBudgetContingencyEvaluator:
    """Tests for DET-BUD-CONTINGENCY evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BudgetContingencyEvaluator()

    def test_adequate_contingency(self, evaluator):
        """Test no finding for adequate contingency (5-20%)."""
        clause = Clause(
            id="C001",
            text="Contingency",
            data={"contingency": 10000, "total_budget": 100000}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_too_low_contingency(self, evaluator):
        """Test finding for contingency below 5%."""
        clause = Clause(
            id="C001",
            text="Contingency",
            data={"contingency": 2000, "total_budget": 100000}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "below minimum" in signal.evidence_summary

    def test_too_high_contingency(self, evaluator):
        """Test finding for contingency above 20%."""
        clause = Clause(
            id="C001",
            text="Contingency",
            data={"contingency": 25000, "total_budget": 100000}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "above maximum" in signal.evidence_summary


class TestBudgetLineItemEvaluator:
    """Tests for DET-BUD-LINEITEM evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BudgetLineItemEvaluator()

    def test_correct_arithmetic(self, evaluator):
        """Test no finding when math is correct."""
        clause = Clause(
            id="C001",
            text="Line item",
            data={"unit_price": 100, "quantity": 10, "line_total": 1000}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_arithmetic_mismatch(self, evaluator):
        """Test finding when calculation doesn't match."""
        clause = Clause(
            id="C001",
            text="Line item",
            data={"unit_price": 100, "quantity": 10, "line_total": 1200}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "deviation_pct" in signal.raw_data


class TestBudgetSumMismatchEvaluator:
    """Tests for DET-BUD-SUM evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BudgetSumMismatchEvaluator()

    def test_sums_match(self, evaluator):
        """Test no finding when budget items sum to contract total."""
        clause = Clause(
            id="C001",
            text="Budget summary",
            data={
                "budget_items": [{"amount": 50000}, {"amount": 50000}],
                "contract_total": 100000
            }
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_sum_exceeds_contract(self, evaluator):
        """Test finding when budget items exceed contract."""
        clause = Clause(
            id="C001",
            text="Budget summary",
            data={
                "budget_items": [{"amount": 60000}, {"amount": 60000}],
                "contract_total": 100000
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["direction"] == "exceeds"

    def test_real_budget_contract_deviation_emits_budget_signal(self, evaluator):
        """TS-COH-BUD-RECON-001: DET-BUD-SUM emits for BOM total vs contract total drift."""
        clause = Clause(
            id="budget-reconciliation",
            text="Project budget vs contract reconciliation",
            data={
                "budget_items": [{"amount": 636_044_805}],
                "contract_total": 628_624_801,
            },
        )

        signal = evaluator.evaluate_v3(clause)

        assert signal is not None
        assert signal.rule_id == "DET-BUD-SUM"
        assert signal.category == "BUDGET"
        assert signal.raw_data["deviation_pct"] == pytest.approx(1.18, abs=0.01)

    def test_within_tolerance_returns_none(self, evaluator):
        """TS-COH-BUD-RECON-001: DET-BUD-SUM stays clean within tolerance."""
        clause = Clause(
            id="budget-reconciliation",
            text="Project budget vs contract reconciliation",
            data={
                "budget_items": [{"amount": 100_500}],
                "contract_total": 100_000,
            },
        )

        assert evaluator.evaluate_v3(clause) is None

    def test_missing_contract_total_returns_none(self, evaluator):
        """TS-COH-BUD-RECON-001: DET-BUD-SUM never fabricates a contract total."""
        clause = Clause(
            id="budget-reconciliation",
            text="Project budget vs contract reconciliation",
            data={"budget_items": [{"amount": 100_500}]},
        )

        assert evaluator.evaluate_v3(clause) is None

    def test_sum_below_contract(self, evaluator):
        """Test finding when budget items are below contract."""
        clause = Clause(
            id="C001",
            text="Budget summary",
            data={
                "budget_items": [{"amount": 30000}, {"amount": 30000}],
                "contract_total": 100000
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["direction"] == "below"


class TestBudgetInternalConsistencyEvaluator:
    """Tests for DET-BUD-INTERNAL evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BudgetInternalConsistencyEvaluator()

    def test_real_budget_declared_total_deviation_emits_budget_signal(self, evaluator):
        """TS-COH-BUD-RECON-004: budget leaf sum is compared to its declared total."""
        clause = Clause(
            id="budget-reconciliation",
            text="Project budget vs declared total reconciliation",
            data={
                "budget_items": [{"amount": 636_044_805}],
                "stated_total": 654_144_805,
            },
        )

        signal = evaluator.evaluate_v3(clause)

        assert signal is not None
        assert signal.rule_id == "DET-BUD-INTERNAL"
        assert signal.category == "BUDGET"
        assert signal.raw_data["items_sum"] == 636_044_805
        assert signal.raw_data["stated_total"] == 654_144_805
        assert signal.raw_data["deviation_pct"] == pytest.approx(2.77, abs=0.01)

    def test_within_tolerance_returns_none(self, evaluator):
        """TS-COH-BUD-RECON-004: declared-total check stays clean within tolerance."""
        clause = Clause(
            id="budget-reconciliation",
            text="Project budget vs declared total reconciliation",
            data={
                "budget_items": [{"amount": 100_500}],
                "stated_total": 100_000,
            },
        )

        assert evaluator.evaluate_v3(clause) is None

    def test_missing_stated_total_returns_none(self, evaluator):
        """TS-COH-BUD-RECON-004: missing stated total is honest-null, not inferred."""
        clause = Clause(
            id="budget-reconciliation",
            text="Project budget vs declared total reconciliation",
            data={"budget_items": [{"amount": 100_500}]},
        )

        assert evaluator.evaluate_v3(clause) is None


class TestRetentionRateEvaluator:
    """Tests for DET-BUD-RETENTION evaluator."""

    @pytest.fixture
    def evaluator(self):
        return RetentionRateEvaluator()

    def test_normal_retention(self, evaluator):
        """Test no finding for normal retention (3-10%)."""
        clause = Clause(id="C001", text="Retention", data={"retention_pct": 0.05})
        assert evaluator.evaluate_v3(clause) is None

    def test_low_retention(self, evaluator):
        """Test finding for retention below 3%."""
        clause = Clause(id="C001", text="Retention", data={"retention_pct": 0.02})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "below minimum" in signal.evidence_summary

    def test_high_retention(self, evaluator):
        """Test finding for retention above 10%."""
        clause = Clause(id="C001", text="Retention", data={"retention_pct": 0.15})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "above maximum" in signal.evidence_summary

    def test_percentage_normalization(self, evaluator):
        """Test that percentages > 1 are normalized (e.g., 5 → 0.05)."""
        clause = Clause(id="C001", text="Retention", data={"retention_pct": 2})  # 2%
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None  # 2% < 3% min


class TestAdvancePaymentEvaluator:
    """Tests for DET-BUD-ADVANCE evaluator."""

    @pytest.fixture
    def evaluator(self):
        return AdvancePaymentEvaluator()

    def test_normal_advance(self, evaluator):
        """Test no finding for advance ≤ 30%."""
        clause = Clause(id="C001", text="Advance", data={"advance_pct": 0.25})
        assert evaluator.evaluate_v3(clause) is None

    def test_high_advance_with_guarantee(self, evaluator):
        """Test finding for high advance with bank guarantee."""
        clause = Clause(
            id="C001",
            text="Advance",
            data={"advance_pct": 0.40, "bank_guarantee": True}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "without bank guarantee" not in signal.evidence_summary

    def test_high_advance_without_guarantee(self, evaluator):
        """Test finding for high advance without bank guarantee."""
        clause = Clause(
            id="C001",
            text="Advance",
            data={"advance_pct": 0.40, "bank_guarantee": False}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "without bank guarantee" in signal.evidence_summary
        # Higher impact without guarantee
        assert signal.impact_score >= 0.55


# ===========================================
# TIME EVALUATOR TESTS
# ===========================================


class TestScheduleStatusEvaluator:
    """Tests for DET-TIM-STATUS evaluator."""

    @pytest.fixture
    def evaluator(self):
        return ScheduleStatusEvaluator()

    @pytest.mark.parametrize("status,expected_impact", [
        ("delayed", 0.70),
        ("behind", 0.65),
        ("at_risk", 0.50),
        ("critical", 0.85),
        ("suspended", 0.80),
        ("cancelled", 0.90),
    ])
    def test_status_impacts(self, evaluator, status: str, expected_impact: float):
        """Test different status values produce correct impacts."""
        clause = Clause(id="C001", text="Schedule", data={"status": status})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.impact_score == expected_impact

    def test_normal_status(self, evaluator):
        """Test no finding for normal statuses."""
        for status in ["on_track", "ahead", "completed", "active"]:
            clause = Clause(id="C001", text="Schedule", data={"status": status})
            assert evaluator.evaluate_v3(clause) is None


class TestDeadlineOverdueEvaluator:
    """Tests for DET-TIM-OVERDUE evaluator."""

    @pytest.fixture
    def evaluator(self):
        return DeadlineOverdueEvaluator()

    def test_future_deadline(self, evaluator):
        """Test no finding for future deadlines."""
        future = date.today() + timedelta(days=30)
        clause = Clause(id="C001", text="Schedule", data={"end_date": str(future)})
        assert evaluator.evaluate_v3(clause) is None

    def test_recent_overdue(self, evaluator):
        """Test finding for recently overdue deadline."""
        past = date.today() - timedelta(days=7)
        clause = Clause(id="C001", text="Schedule", data={"end_date": str(past)})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["days_overdue"] == 7

    def test_severely_overdue(self, evaluator):
        """Test high impact for severely overdue deadline."""
        past = date.today() - timedelta(days=90)
        clause = Clause(id="C001", text="Schedule", data={"end_date": str(past)})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.impact_score >= 0.70


class TestMilestoneGapEvaluator:
    """Tests for DET-TIM-GAP evaluator."""

    @pytest.fixture
    def evaluator(self):
        return MilestoneGapEvaluator()

    def test_acceptable_gaps(self, evaluator):
        """Test no finding for gaps within 90 days."""
        milestones = [
            {"date": str(date.today())},
            {"date": str(date.today() + timedelta(days=60))},
            {"date": str(date.today() + timedelta(days=120))},
        ]
        clause = Clause(id="C001", text="Schedule", data={"milestones": milestones})
        assert evaluator.evaluate_v3(clause) is None

    def test_excessive_gap(self, evaluator):
        """Test finding for gaps exceeding 90 days."""
        milestones = [
            {"date": str(date.today())},
            {"date": str(date.today() + timedelta(days=150))},
        ]
        clause = Clause(id="C001", text="Schedule", data={"milestones": milestones})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["max_gap_days"] == 150


class TestPredecessorOverlapEvaluator:
    """Tests for DET-TIM-PREDECESSOR evaluator."""

    @pytest.fixture
    def evaluator(self):
        return PredecessorOverlapEvaluator()

    def test_valid_sequence(self, evaluator):
        """Test no finding for valid predecessor sequence."""
        items = [
            {"id": "T1", "name": "Task 1", "end_date": str(date.today())},
            {
                "id": "T2",
                "name": "Task 2",
                "predecessor_id": "T1",
                "start_date": str(date.today() + timedelta(days=1)),
            },
        ]
        clause = Clause(id="C001", text="Schedule", data={"schedule_items": items})
        assert evaluator.evaluate_v3(clause) is None

    def test_overlap_detected(self, evaluator):
        """Test finding when task starts before predecessor ends."""
        items = [
            {"id": "T1", "name": "Task 1", "end_date": str(date.today() + timedelta(days=10))},
            {
                "id": "T2",
                "name": "Task 2",
                "predecessor_id": "T1",
                "start_date": str(date.today()),
            },
        ]
        clause = Clause(id="C001", text="Schedule", data={"schedule_items": items})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["overlap_days"] == 10


class TestScheduleDurationEvaluator:
    """Tests for DET-TIM-DURATION evaluator."""

    @pytest.fixture
    def evaluator(self):
        return ScheduleDurationEvaluator()

    def test_end_before_start(self, evaluator):
        """Test finding when end date is before start date."""
        clause = Clause(
            id="C001",
            text="Task",
            data={
                "start_date": str(date.today()),
                "end_date": str(date.today() - timedelta(days=1)),
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.impact_score == 0.90

    def test_insufficient_buffer(self, evaluator):
        """Test finding for insufficient buffer days."""
        clause = Clause(id="C001", text="Task", data={"buffer_days": 3})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "Buffer" in signal.evidence_summary


# ===========================================
# LEGAL EVALUATOR TESTS
# ===========================================


class TestContractReviewOverdueEvaluator:
    """Tests for DET-LEG-REVIEW evaluator."""

    @pytest.fixture
    def evaluator(self):
        return ContractReviewOverdueEvaluator()

    def test_recent_review(self, evaluator):
        """Test no finding for recent review."""
        recent = date.today() - timedelta(days=100)
        clause = Clause(id="C001", text="Legal", data={"last_review_date": str(recent)})
        assert evaluator.evaluate_v3(clause) is None

    def test_overdue_review(self, evaluator):
        """Test finding for review overdue (>365 days)."""
        old = date.today() - timedelta(days=400)
        clause = Clause(id="C001", text="Legal", data={"last_review_date": str(old)})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["days_since"] == 400


class TestPenaltyCapEvaluator:
    """Tests for DET-LEG-PENALTY evaluator."""

    @pytest.fixture
    def evaluator(self):
        return PenaltyCapEvaluator()

    def test_no_cap(self, evaluator):
        """Test finding for missing penalty cap."""
        clause = Clause(id="C001", text="Penalty", data={"has_penalty_cap": False})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "unlimited liability" in signal.evidence_summary

    def test_excessive_cap(self, evaluator):
        """Test finding for excessive penalty cap (>15%)."""
        clause = Clause(id="C001", text="Penalty", data={"penalty_cap_pct": 0.25})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None

    def test_reasonable_cap(self, evaluator):
        """Test no finding for reasonable cap."""
        clause = Clause(id="C001", text="Penalty", data={"penalty_cap_pct": 0.10})
        assert evaluator.evaluate_v3(clause) is None


class TestNoticePeriodEvaluator:
    """Tests for DET-LEG-NOTICE evaluator."""

    @pytest.fixture
    def evaluator(self):
        return NoticePeriodEvaluator()

    def test_normal_notice(self, evaluator):
        """Test no finding for normal notice period."""
        clause = Clause(id="C001", text="Notice", data={"notice_period_days": 30})
        assert evaluator.evaluate_v3(clause) is None

    def test_too_short_notice(self, evaluator):
        """Test finding for notice period < 14 days."""
        clause = Clause(id="C001", text="Notice", data={"notice_period_days": 7})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "< min" in signal.evidence_summary

    def test_too_long_notice(self, evaluator):
        """Test finding for notice period > 90 days."""
        clause = Clause(id="C001", text="Notice", data={"notice_period_days": 120})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


class TestWarrantyPeriodEvaluator:
    """Tests for DET-LEG-WARRANTY evaluator."""

    @pytest.fixture
    def evaluator(self):
        return WarrantyPeriodEvaluator()

    def test_normal_warranty(self, evaluator):
        """Test no finding for normal warranty period."""
        clause = Clause(id="C001", text="Warranty", data={"warranty_months": 12})
        assert evaluator.evaluate_v3(clause) is None

    def test_too_short_warranty(self, evaluator):
        """Test finding for warranty < 6 months."""
        clause = Clause(id="C001", text="Warranty", data={"warranty_months": 3})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "< min" in signal.evidence_summary


class TestPaymentTermEvaluator:
    """Tests for DET-LEG-PAYMENT evaluator."""

    @pytest.fixture
    def evaluator(self):
        return PaymentTermEvaluator()

    def test_normal_payment_term(self, evaluator):
        """Test no finding for payment term ≤ 60 days."""
        clause = Clause(id="C001", text="Payment", data={"payment_term_days": 45})
        assert evaluator.evaluate_v3(clause) is None

    def test_long_payment_term(self, evaluator):
        """Test finding for payment term > 60 days."""
        clause = Clause(id="C001", text="Payment", data={"payment_term_days": 90})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


class TestInsuranceExpiryEvaluator:
    """Tests for DET-LEG-INSURANCE evaluator."""

    @pytest.fixture
    def evaluator(self):
        return InsuranceExpiryEvaluator()

    def test_valid_insurance(self, evaluator):
        """Test no finding for valid insurance coverage."""
        expiry = date.today() + timedelta(days=180)
        clause = Clause(id="C001", text="Insurance", data={"insurance_expiry": str(expiry)})
        assert evaluator.evaluate_v3(clause) is None

    def test_expired_insurance(self, evaluator):
        """Test finding for expired insurance."""
        expiry = date.today() - timedelta(days=30)
        clause = Clause(id="C001", text="Insurance", data={"insurance_expiry": str(expiry)})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "expired" in signal.evidence_summary

    def test_expiring_soon(self, evaluator):
        """Test finding for insurance expiring within warning period."""
        expiry = date.today() + timedelta(days=30)  # Within 60-day warning
        clause = Clause(id="C001", text="Insurance", data={"insurance_expiry": str(expiry)})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


# ===========================================
# TECHNICAL EVALUATOR TESTS
# ===========================================


class TestBomLeadTimeEvaluator:
    """Tests for DET-TEC-LEADTIME evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BomLeadTimeEvaluator()

    def test_adequate_lead_time(self, evaluator):
        """Test no finding when lead time is adequate."""
        needed = date.today() + timedelta(days=60)
        clause = Clause(
            id="C001",
            text="BOM",
            data={
                "lead_time_days": 30,
                "required_on_site_date": str(needed),
                "item_name": "Steel beams"
            }
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_tight_lead_time(self, evaluator):
        """Test finding when ordering window is tight."""
        needed = date.today() + timedelta(days=35)
        clause = Clause(
            id="C001",
            text="BOM",
            data={
                "lead_time_days": 30,
                "required_on_site_date": str(needed),
                "item_name": "Steel beams"
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "left to order" in signal.evidence_summary

    def test_missed_ordering_window(self, evaluator):
        """Test finding when ordering window has closed."""
        needed = date.today() + timedelta(days=20)
        clause = Clause(
            id="C001",
            text="BOM",
            data={
                "lead_time_days": 30,
                "required_on_site_date": str(needed),
                "item_name": "Steel beams"
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "ordering window closed" in signal.evidence_summary


class TestSpecReferenceEvaluator:
    """Tests for DET-TEC-SPEC evaluator."""

    @pytest.fixture
    def evaluator(self):
        return SpecReferenceEvaluator()

    def test_has_spec_reference(self, evaluator):
        """Test no finding when spec reference exists."""
        clause = Clause(
            id="C001",
            text="Materials",
            data={"category": "TECHNICAL", "spec_reference": "ISO 9001"}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_missing_spec_reference(self, evaluator):
        """Test finding when technical clause lacks spec reference."""
        clause = Clause(
            id="C001",
            text="Materials",
            data={"category": "TECHNICAL", "material": "concrete"}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


class TestBomBudgetLinkEvaluator:
    """Tests for DET-TEC-BOMBUDGET evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BomBudgetLinkEvaluator()

    def test_all_linked(self, evaluator):
        """Test no finding when all BOM items have budget links."""
        bom_items = [
            {"item_name": "Steel", "budget_item_id": "B001"},
            {"item_name": "Concrete", "budget_item_id": "B002"},
        ]
        clause = Clause(id="C001", text="BOM", data={"bom_items": bom_items})
        assert evaluator.evaluate_v3(clause) is None

    def test_unlinked_items(self, evaluator):
        """Test finding when BOM items lack budget links."""
        bom_items = [
            {"item_name": "Steel", "budget_item_id": "B001"},
            {"item_name": "Concrete"},  # Missing budget link
        ]
        clause = Clause(id="C001", text="BOM", data={"bom_items": bom_items})
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data["unlinked_count"] == 1


# ===========================================
# QUALITY EVALUATOR TESTS
# ===========================================


class TestQualityStandardEvaluator:
    """Tests for DET-QUA-STANDARD evaluator."""

    @pytest.fixture
    def evaluator(self):
        return QualityStandardEvaluator()

    def test_specific_standard(self, evaluator):
        """Test no finding when specific standards are cited."""
        clause = Clause(
            id="C001",
            text="Quality control per ISO 9001 requirements",
            data={}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_vague_standard(self, evaluator):
        """Test finding for vague 'industry standards' reference.

        DET-QUA-STANDARD only fires when infer_category resolves the clause
        to QUALITY/TECHNICAL (category-targeted retrieval, TASK-BCK-057/058).
        The original text ("Work shall comply with...") ties 1-1-1 across
        SCOPE/TECHNICAL/QUALITY on keyword count and resolves to SCOPE by
        dict-order tie-break, so the rule never fires. Adding "Quality" gives
        an unambiguous QUALITY match while preserving the vague-standard intent.
        """
        clause = Clause(
            id="C001",
            text="Quality of work shall comply with industry standards and best practices",
            data={}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


class TestInspectionFrequencyEvaluator:
    """Tests for DET-QUA-INSPECT evaluator."""

    @pytest.fixture
    def evaluator(self):
        return InspectionFrequencyEvaluator()

    def test_complete_inspection_clause(self, evaluator):
        """Test no finding when inspection frequency and method are defined."""
        clause = Clause(
            id="C001",
            text="Quality inspection",
            data={
                "inspection": True,
                "inspection_frequency": "weekly",
                "inspection_method": "visual"
            }
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_incomplete_inspection_clause(self, evaluator):
        """Test finding when inspection clause lacks frequency."""
        clause = Clause(
            id="C001",
            text="Quality inspection required",
            data={"inspection": True}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert "frequency" in signal.raw_data["missing_fields"]


# ===========================================
# SCOPE EVALUATOR TESTS
# ===========================================


class TestMissingRequiredFieldsEvaluator:
    """Tests for DET-SCP-MISSING evaluator."""

    @pytest.fixture
    def evaluator(self):
        return MissingRequiredFieldsEvaluator()

    def test_complete_budget_clause(self, evaluator):
        """Test no finding when all required budget fields exist."""
        clause = Clause(
            id="C001",
            text="Budget",
            data={"planned": 100000, "currency": "USD", "current": 95000}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_missing_budget_fields(self, evaluator):
        """Test finding for missing budget fields."""
        clause = Clause(
            id="C001",
            text="Budget",
            data={"current": 95000}  # Missing: planned, currency
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


class TestScopeDeliverablesEvaluator:
    """Tests for DET-SCP-DELIVERABLES evaluator."""

    @pytest.fixture
    def evaluator(self):
        return ScopeDeliverablesEvaluator()

    def test_structured_deliverables(self, evaluator):
        """Test no finding when deliverables are structured."""
        clause = Clause(
            id="C001",
            text="Scope of work",
            data={"deliverables": [{"name": "Foundation"}, {"name": "Structure"}]}
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_unstructured_deliverables(self, evaluator):
        """Test finding when scope mentions deliverables without structure."""
        clause = Clause(
            id="C001",
            text="The scope includes all deliverables for the project",
            data={}
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


# ===========================================
# CROSS-DIMENSIONAL EVALUATOR TESTS
# ===========================================


class TestBudgetVsContractTotalEvaluator:
    """Tests for DET-CRS-BUDCON evaluator."""

    @pytest.fixture
    def evaluator(self):
        return BudgetVsContractTotalEvaluator()

    def test_aligned_totals(self, evaluator):
        """Test no finding when budget and contract align."""
        clause = Clause(
            id="C001",
            text="Contract",
            data={
                "budget_items": [{"amount": 50000}, {"amount": 50000}],
                "contract_total": 100000
            }
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_rule_id_override(self, evaluator):
        """Test that rule_id is correctly overridden to DET-CRS-BUDCON."""
        clause = Clause(
            id="C001",
            text="Contract",
            data={
                "budget_items": [{"amount": 70000}, {"amount": 70000}],
                "contract_total": 100000
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.rule_id == "DET-CRS-BUDCON"


class TestScheduleVsBomDeliveryEvaluator:
    """Tests for DET-CRS-SCHBOM evaluator."""

    @pytest.fixture
    def evaluator(self):
        return ScheduleVsBomDeliveryEvaluator()

    def test_aligned_delivery(self, evaluator):
        """Test no finding when BOM delivery aligns with schedule."""
        start = date.today()
        end = date.today() + timedelta(days=180)
        clause = Clause(
            id="C001",
            text="Schedule",
            data={
                "schedule_items": [
                    {"start_date": str(start), "end_date": str(end)}
                ],
                "bom_items": [
                    {"item_name": "Steel", "required_on_site_date": str(start + timedelta(days=30))}
                ]
            }
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_out_of_window_delivery(self, evaluator):
        """Test finding when BOM delivery is outside schedule window."""
        start = date.today()
        end = date.today() + timedelta(days=180)
        clause = Clause(
            id="C001",
            text="Schedule",
            data={
                "schedule_items": [
                    {"start_date": str(start), "end_date": str(end)}
                ],
                "bom_items": [
                    {"item_name": "Steel", "required_on_site_date": str(start - timedelta(days=30))}
                ]
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


class TestScopeVsBudgetCoverageEvaluator:
    """Tests for DET-CRS-SCPBUD evaluator."""

    @pytest.fixture
    def evaluator(self):
        return ScopeVsBudgetCoverageEvaluator()

    def test_full_coverage(self, evaluator):
        """Test no finding when all deliverables have budget coverage."""
        clause = Clause(
            id="C001",
            text="Scope",
            data={
                "deliverables": [
                    {"name": "Foundation", "budget_item_id": "B001"}
                ],
                "budget_items": [{"id": "B001", "name": "Foundation"}]
            }
        )
        assert evaluator.evaluate_v3(clause) is None

    def test_unfunded_deliverables(self, evaluator):
        """Test finding when deliverables lack budget coverage."""
        clause = Clause(
            id="C001",
            text="Scope",
            data={
                "deliverables": [
                    {"name": "Foundation"},
                    {"name": "Structure"}
                ],
                "budget_items": [{"id": "B001", "name": "Other"}]
            }
        )
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None


# ===========================================
# REGISTRY TESTS
# ===========================================


class TestEvaluatorRegistry:
    """Tests for the evaluator registry function."""

    def test_registry_returns_27_evaluators(self):
        """Test that get_all_deterministic_evaluators returns exactly 27 evaluators."""
        evaluators = get_all_deterministic_evaluators()
        assert len(evaluators) == 27

    def test_all_evaluators_have_metadata(self):
        """Test that all evaluators have required metadata."""
        evaluators = get_all_deterministic_evaluators()
        for ev in evaluators:
            assert ev.rule_id.startswith("DET-")
            assert ev.rule_name != "Unknown Rule"
            assert ev.category in ("BUDGET", "TIME", "LEGAL", "SCOPE", "TECHNICAL", "QUALITY")

    def test_evaluator_categories(self):
        """Test evaluators are distributed across categories."""
        evaluators = get_all_deterministic_evaluators()
        categories = {}
        for ev in evaluators:
            categories[ev.category] = categories.get(ev.category, 0) + 1

        assert categories.get("BUDGET", 0) >= 6
        assert categories.get("TIME", 0) >= 5
        assert categories.get("LEGAL", 0) >= 6
        assert categories.get("TECHNICAL", 0) >= 3
        assert categories.get("QUALITY", 0) >= 2
        assert categories.get("SCOPE", 0) >= 2

    def test_custom_config_propagates(self):
        """Test that custom config is passed to evaluators."""
        config = EvaluatorConfig(budget_overrun_warning_pct=0.10)
        evaluators = get_all_deterministic_evaluators(config)

        # Find the budget overrun evaluator and check its config
        for ev in evaluators:
            if isinstance(ev, BudgetOverrunEvaluator):
                assert ev.config.budget_overrun_warning_pct == 0.10
                break
        else:
            pytest.fail("BudgetOverrunEvaluator not found in registry")

    def test_all_evaluators_have_evaluate_v3(self):
        """Test that all evaluators implement evaluate_v3."""
        evaluators = get_all_deterministic_evaluators()
        clause = Clause(id="TEST", text="Test", data={})

        for ev in evaluators:
            # Should not raise - all have evaluate_v3
            result = ev.evaluate_v3(clause)
            # Result should be None or FindingSignal
            assert result is None or isinstance(result, FindingSignal)


# ===========================================
# BACKWARD COMPATIBILITY TESTS
# ===========================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy API."""

    def test_schedule_delay_alias(self):
        """Test that ScheduleDelayEvaluator is aliased to ScheduleStatusEvaluator."""
        from src.coherence.rules_engine.deterministic import ScheduleDelayEvaluator
        assert ScheduleDelayEvaluator is ScheduleStatusEvaluator

    def test_legacy_evaluate_method(self):
        """Test that evaluate() method still works for legacy compatibility."""
        evaluator = BudgetOverrunEvaluator()
        clause = Clause(
            id="C001",
            text="Budget",
            data={"current": 120000, "planned": 100000}
        )
        finding = evaluator.evaluate(clause)
        assert finding is not None
        assert finding.triggered_clause.id == "C001"
