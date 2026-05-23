from datetime import date

import pytest

from src.coherence.domain.ports.coherence_llm_gate_port import GateDecision
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.models import Clause, FindingSignal

_RULE_IDS = (
    "R-SCOPE-CLARITY-01", "R-PAYMENT-CLARITY-01", "R-SCHEDULE-CLARITY-01",
    "R-TECHNICAL-SPEC-CLARITY-01", "R-RESPONSIBILITY-01", "R-QUALITY-STANDARDS-01",
)


class FakeGate:
    """Returns canned decisions keyed by (rule_id, clause_id). No DB."""
    def __init__(self, decisions):
        self.decisions = decisions
        self.calls = []
    async def evaluate_rule(self, tenant_id, rule_id, clause):
        self.calls.append((tenant_id, rule_id, clause.id))
        return self.decisions[(rule_id, clause.id)]


def _finding(rule_id, clause_id, category):
    return FindingSignal(
        rule_id=rule_id, clause_id=clause_id, impact_score=0.5,
        confidence=0.9, severity="medium", category=category,
        evidence_summary="e", quote="q", raw_data={},
    )


def _rolled_off(cache_key):
    return GateDecision(
        state="rolled_out_off", finding=None, reason="rule_rollout_disabled",
        reset_date=None, cache_key=cache_key, cost_charged_usd=0.0,
    )


@pytest.mark.asyncio
async def test_node_uses_gate_findings_and_marks_coverage_evaluated():
    from src.coherence.graph.nodes import llm_semantic_evaluate_async
    clause = Clause(id="c1", text="ambiguous", data={})
    state = CoherenceGraphState(
        project_id="p", clauses=[clause],
        config=EvaluationConfig(tenant_id="00000000-0000-0000-0000-000000000001"),
    )
    decisions: dict[tuple[str, str], GateDecision] = {
        ("R-SCOPE-CLARITY-01", "c1"): GateDecision(
            state="evaluated",
            finding=_finding("R-SCOPE-CLARITY-01", "c1", "SCOPE"),
            reason=None, reset_date=None, cache_key="k1", cost_charged_usd=0.0007,
        ),
    }
    for rid in _RULE_IDS:
        decisions.setdefault((rid, "c1"), _rolled_off(f"k-{rid}"))

    out = await llm_semantic_evaluate_async(state, gate=FakeGate(decisions))

    assert any(s.rule_id == "R-SCOPE-CLARITY-01" for s in out["llm_signals"])
    assert out["coverage_map"]["SCOPE"] is True
    # Other categories rolled off → False (not True)
    for cat in ("BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"):
        assert out["coverage_map"].get(cat, False) is False


@pytest.mark.asyncio
async def test_node_emits_single_advisory_when_any_rule_budget_exhausted():
    from src.coherence.graph.nodes import llm_semantic_evaluate_async
    reset = date(2026, 6, 1)
    clause = Clause(id="c1", text="x", data={})
    state = CoherenceGraphState(
        project_id="p", clauses=[clause],
        config=EvaluationConfig(tenant_id="00000000-0000-0000-0000-000000000001"),
    )
    gate = FakeGate({
        (rid, "c1"): GateDecision(
            state="budget_exhausted", finding=None,
            reason="tenant_budget_exhausted", reset_date=reset,
            cache_key=None, cost_charged_usd=0.0,
        )
        for rid in _RULE_IDS
    })
    out = await llm_semantic_evaluate_async(state, gate=gate)

    # Exactly ONE advisory alert per evaluation, with the earliest reset_date.
    adv = [a for a in out.get("alerts", []) if a.rule_id == "ADV-BUDGET-EXHAUSTED"]
    assert len(adv) == 1
    assert out.get("budget_exhausted_reset_date") == reset
    assert out["llm_signals"] == []


@pytest.mark.asyncio
async def test_node_low_budget_escape_hatch_still_works():
    """Setting config.low_budget_mode=True bypasses the gate entirely (test escape)."""
    from src.coherence.graph.nodes import llm_semantic_evaluate_async
    clause = Clause(id="c1", text="x", data={})
    state = CoherenceGraphState(
        project_id="p", clauses=[clause],
        config=EvaluationConfig(low_budget_mode=True,
                                tenant_id="00000000-0000-0000-0000-000000000001"),
    )
    # gate=None is fine — the escape hatch returns before any gate construction.
    out = await llm_semantic_evaluate_async(state, gate=None)
    assert out["llm_signals"] == []
    assert out["llm_cost_usd"] == 0.0
    # coverage_map carries the 6 categories as False (LLM layer didn't run)
    cov = out["coverage_map"]
    for cat in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"):
        assert cov.get(cat) is False


def test_evaluation_config_low_budget_mode_default_is_false():
    """P3: always-on LLM semantic layer; default flipped from True → False."""
    from src.coherence.graph.state import EvaluationConfig
    cfg = EvaluationConfig()
    assert cfg.low_budget_mode is False
