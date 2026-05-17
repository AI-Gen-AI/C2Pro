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
