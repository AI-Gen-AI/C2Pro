from src.coherence.models import Clause
from src.coherence.rules_engine.base import ApplicabilityState, RuleEvaluator


def test_applicability_state_enum_values():
    assert ApplicabilityState.EVALUATED.value == "EVALUATED"
    assert ApplicabilityState.SKIPPED_MISSING_INPUTS.value == "SKIPPED_MISSING_INPUTS"
    assert ApplicabilityState.SKIPPED_DISABLED.value == "SKIPPED_DISABLED"


def test_base_default_evaluated_when_category_matches():
    c = Clause(id="t1", text="BOM material standard specification required.", data={})

    class _Bare(RuleEvaluator):
        rule_id = "X"
        category = "TECHNICAL"
        def evaluate(self, clause):
            return None
    assert _Bare().applicability(c) == ApplicabilityState.EVALUATED


def test_base_default_skips_when_category_mismatch():
    c = Clause(id="t2", text="Insurance policy certificate.", data={})

    class _Bare(RuleEvaluator):
        rule_id = "X"
        category = "TECHNICAL"
        def evaluate(self, clause):
            return None
    assert _Bare().applicability(c) == ApplicabilityState.SKIPPED_MISSING_INPUTS


def test_llm_evaluator_skipped_disabled_in_low_budget():
    from src.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator
    ev = LlmRuleEvaluator(
        rule_id="R-RESPONSIBILITY-01", rule_name="Resp", rule_description="d",
        detection_logic="l", category="legal", low_budget_mode=True,
    )
    c = Clause(id="l1", text="The contractor shall be liable.", data={})
    assert ev.applicability(c) == ApplicabilityState.SKIPPED_DISABLED


def test_llm_evaluator_evaluated_when_enabled():
    from src.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator
    ev = LlmRuleEvaluator(
        rule_id="R-RESPONSIBILITY-01", rule_name="Resp", rule_description="d",
        detection_logic="l", category="legal", low_budget_mode=False,
    )
    c = Clause(id="l1", text="The contractor shall be liable.", data={})
    assert ev.applicability(c) == ApplicabilityState.EVALUATED


import pytest

from src.coherence.rules_engine import deterministic as D
from src.coherence.rules_engine.base import ApplicabilityState as A


@pytest.mark.parametrize("evaluator_cls,data,text,expected", [
    (D.BudgetOverrunEvaluator, {"current": 110.0, "planned": 100.0}, "cost", A.EVALUATED),
    (D.BudgetOverrunEvaluator, {}, "cost overrun", A.SKIPPED_MISSING_INPUTS),
    (D.BudgetLineItemEvaluator, {"unit_price": 2.0, "quantity": 3.0, "line_total": 6.0}, "x", A.EVALUATED),
    (D.BudgetLineItemEvaluator, {"unit_price": 2.0}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.BomBudgetLinkEvaluator, {"bom_items": [{"item_name": "pump"}]}, "x", A.EVALUATED),
    (D.BomBudgetLinkEvaluator, {"bom_items": []}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.SpecReferenceEvaluator, {"material": "concrete"}, "x", A.EVALUATED),
    (D.SpecReferenceEvaluator, {}, "party name", A.SKIPPED_MISSING_INPUTS),
    (D.NoticePeriodEvaluator, {"notice_period_days": 30}, "x", A.EVALUATED),
    (D.NoticePeriodEvaluator, {}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.PenaltyCapEvaluator, {"has_penalty_cap": False}, "x", A.EVALUATED),
    (D.PenaltyCapEvaluator, {}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.ScheduleStatusEvaluator, {"status": "delayed"}, "schedule milestone delay", A.EVALUATED),
    (D.ScheduleStatusEvaluator, {"status": "delayed"}, "payment price invoice", A.SKIPPED_MISSING_INPUTS),
    (D.ScheduleDurationEvaluator, {"start_date": "2026-01-01", "end_date": "2026-02-01"}, "x", A.EVALUATED),
    (D.ScheduleDurationEvaluator, {}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.ScopeVsBudgetCoverageEvaluator, {"deliverables": [{"name": "a"}], "budget_items": [{"id": "b"}]}, "x", A.EVALUATED),
    (D.ScopeVsBudgetCoverageEvaluator, {"deliverables": []}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.ScopeDeliverablesEvaluator, {}, "scope of work deliverable", A.EVALUATED),
    (D.ScopeDeliverablesEvaluator, {}, "insurance policy", A.SKIPPED_MISSING_INPUTS),
    (D.QualityStandardEvaluator, {}, "quality inspection standard", A.EVALUATED),
    (D.QualityStandardEvaluator, {}, "payment terms price", A.SKIPPED_MISSING_INPUTS),
    (D.InspectionFrequencyEvaluator, {}, "quality control inspection", A.EVALUATED),
    (D.InspectionFrequencyEvaluator, {}, "payment advance guarantee", A.SKIPPED_MISSING_INPUTS),
])
def test_deterministic_applicability(evaluator_cls, data, text, expected):
    from src.coherence.models import Clause
    c = Clause(id="c", text=text, data=data)
    assert evaluator_cls().applicability(c) == expected
