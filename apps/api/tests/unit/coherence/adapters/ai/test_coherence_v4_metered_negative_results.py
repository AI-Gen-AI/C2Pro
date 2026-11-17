"""V4 Front B: negative Coherence findings may still have billable LLM use."""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
from src.coherence.adapters.ai.llm_rule_evaluator import LLMRuleEvaluatorAdapter
from src.coherence.models import Clause
from src.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator


class MeteredWrapper:
    def __init__(self, impact: float, *, cost: float = 0.017, cached: bool = False):
        self.impact = impact
        self.cost = cost
        self.cached = cached
        self.calls = []

    async def generate(self, request):
        self.calls.append(request)
        return SimpleNamespace(
            content=json.dumps({
                "impact_score": self.impact,
                "confidence": 0.93,
                "rule_violated": self.impact > 0,
                "evidence": {
                    "quote": "The supplier provides monthly status.",
                    "explanation": "The clause may or may not breach the rule.",
                },
                "recommendation": "Verify contract alignment",
            }),
            model_used="test-only-coherence",
            cached=self.cached,
            cost_usd=self.cost,
            input_tokens=375,
            output_tokens=95,
        )


def _evaluator(wrapper):
    return LlmRuleEvaluator(
        rule_id="R-SCOPE-TEST",
        rule_name="Scope clarity",
        rule_description="Check scoped obligations",
        detection_logic="Assess context, not keywords",
        category="scope",
        tenant_id=uuid4(),
        llm_port=LLMRuleEvaluatorAdapter(wrapper=wrapper),
    )


def _clause():
    return Clause(
        id="C-TEST", text="The supplier provides monthly status.",
        data={},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("impact", [0.0, 0.85])
async def test_both_positive_and_negative_rule_evaluations_capture_real_usage(impact):
    wrapper = MeteredWrapper(impact)
    evaluator = _evaluator(wrapper)
    result = await evaluator.evaluate_v3_async(_clause())
    if impact == 0:
        assert result is None
    else:
        assert result is not None
    assert evaluator.total_cost_usd == pytest.approx(0.017)
    assert evaluator.llm_calls_count == 1
    assert evaluator._last_call_metrics == {
        "model": "test-only-coherence",
        "input_tokens": 375,
        "output_tokens": 95,
        "cost_usd": 0.017,
        "cached": False,
        "billing_status": "METERED",
    }
    assert len(wrapper.calls) == 1


@pytest.mark.asyncio
async def test_coherence_gate_accounts_negative_result_as_billable(monkeypatch):
    from src.coherence.rules_engine import registry

    wrapper = MeteredWrapper(0)
    evaluator = _evaluator(wrapper)
    monkeypatch.setattr(
        registry, "get_v1_evaluator",
        lambda *args, **kwargs: evaluator,
    )
    monkeypatch.setenv("C2PRO_COHERENCE_STRICT_METERING", "1")
    signal, input_tokens, output_tokens, cost, _latency, model = (
        await CoherenceLlmGate()._call_rule_via_llm(
            "R-SCOPE-TEST", _clause(), tenant_id=str(evaluator.tenant_id),
        )
    )
    assert signal is None
    assert input_tokens == 375 and output_tokens == 95
    assert cost == pytest.approx(0.017)
    assert model == "test-only-coherence"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["zero_price", "unknown_receipt"])
async def test_strict_coherence_refuses_unverified_zero_charge(monkeypatch, kind):
    from src.coherence.rules_engine import registry

    class MissingReceiptEvaluator:
        total_cost_usd = 0.0
        _last_call_metrics = (
            {"billing_status": "METERED", "input_tokens": 100,
             "output_tokens": 20, "cached": False}
            if kind == "zero_price" else {"billing_status": "UNKNOWN"}
        )

        async def evaluate_v3_async(self, clause):
            return None

    monkeypatch.setattr(
        registry, "get_v1_evaluator",
        lambda *args, **kwargs: MissingReceiptEvaluator(),
    )
    monkeypatch.setenv("C2PRO_COHERENCE_STRICT_METERING", "1")
    with pytest.raises(RuntimeError, match="usage unverified"):
        await CoherenceLlmGate()._call_rule_via_llm(
            "R-SCOPE-TEST", _clause(), tenant_id=str(uuid4()),
        )


@pytest.mark.asyncio
async def test_strict_metering_never_reuses_prior_receipt_after_provider_failure(
    monkeypatch,
):
    from src.coherence.rules_engine import registry

    class FailingPort:
        async def evaluate(self, **kwargs):
            raise TimeoutError("synthetic provider timeout")

    evaluator = LlmRuleEvaluator(
        rule_id="R-SCOPE-TEST",
        rule_name="Scope clarity",
        rule_description="Check scoped obligations",
        detection_logic="Assess obligations",
        category="scope",
        llm_port=FailingPort(),
    )
    evaluator._last_call_metrics = {
        "billing_status": "METERED", "input_tokens": 100,
        "output_tokens": 50, "cost_usd": 0.03,
    }
    monkeypatch.setattr(
        registry, "get_v1_evaluator", lambda *args, **kwargs: evaluator,
    )
    monkeypatch.setenv("C2PRO_COHERENCE_STRICT_METERING", "1")
    with pytest.raises(RuntimeError, match="usage unverified"):
        await CoherenceLlmGate()._call_rule_via_llm(
            "R-SCOPE-TEST", _clause(), tenant_id=str(uuid4()),
        )
    assert evaluator._last_call_metrics["billing_status"] == "UNKNOWN"
