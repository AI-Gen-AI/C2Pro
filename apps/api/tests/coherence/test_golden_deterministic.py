"""
Suite ID: TS-COH-DET-GOLDEN-002

Golden deterministic evaluator tests using calibration-style cases.
"""

import pytest

from src.coherence.models import Clause
from src.coherence.rules_engine.deterministic import get_all_deterministic_evaluators

from tests.coherence.golden_deterministic import GOLDEN_CASES


@pytest.fixture
def evaluators():
    return get_all_deterministic_evaluators()


class TestGoldenDeterministicCases:
    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["case_id"])
    def test_golden_cases_have_expected_findings_count(self, case, evaluators):
        clauses = [Clause(**payload) for payload in case["clauses"]]

        all_signals = []
        for clause in clauses:
            for evaluator in evaluators:
                signal = evaluator.evaluate_v3(clause)
                if signal:
                    all_signals.append(signal)

        assert len(all_signals) == case["expected_findings"]

    @pytest.mark.parametrize(
        "case",
        [case for case in GOLDEN_CASES if case["expected_rules_triggered"]],
        ids=lambda case: case["case_id"],
    )
    def test_golden_cases_trigger_expected_rules(self, case, evaluators):
        clauses = [Clause(**payload) for payload in case["clauses"]]

        triggered_rule_ids = set()
        for clause in clauses:
            for evaluator in evaluators:
                signal = evaluator.evaluate_v3(clause)
                if signal:
                    triggered_rule_ids.add(signal.rule_id)

        assert triggered_rule_ids.issuperset(case["expected_rules_triggered"])
