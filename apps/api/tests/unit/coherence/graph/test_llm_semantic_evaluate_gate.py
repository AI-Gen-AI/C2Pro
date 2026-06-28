import logging
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
    clause = Clause(
        id="c1",
        text=(
            "The contractor shall perform work as necessary and appropriate "
            "without objective acceptance criteria."
        ),
        data={},
    )
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
    clause = Clause(
        id="c1",
        text="The contractor shall perform work as necessary under the contract.",
        data={},
    )
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


def test_nodes_logger_emits_info_by_default_for_live_gate_summary():
    """TASK-COH-LLM-APPLIC-009-P3: stdlib INFO gate summaries must be observable
    in default application logs without requiring DEBUG logging."""
    from src.coherence.graph import nodes

    assert nodes.logger.isEnabledFor(logging.INFO)
    assert any(isinstance(handler, logging.StreamHandler) for handler in nodes.logger.handlers)


_RULE_CATEGORY = {
    "R-SCOPE-CLARITY-01": "SCOPE", "R-PAYMENT-CLARITY-01": "BUDGET",
    "R-SCHEDULE-CLARITY-01": "TIME", "R-TECHNICAL-SPEC-CLARITY-01": "TECHNICAL",
    "R-RESPONSIBILITY-01": "LEGAL", "R-QUALITY-STANDARDS-01": "QUALITY",
}


class RecordingGate:
    """Records every (rule_id, clause_id) reaching the gate; returns a benign
    'evaluated' finding so coverage is marked for whatever actually runs."""
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def evaluate_rule(self, tenant_id, rule_id, clause):
        self.calls.append((rule_id, clause.id))
        return GateDecision(
            state="evaluated",
            finding=_finding(rule_id, clause.id, _RULE_CATEGORY[rule_id]),
            reason=None, reset_date=None, cache_key="k", cost_charged_usd=0.0,
        )


@pytest.mark.asyncio
async def test_run_gate_skips_llm_rules_for_irrelevant_clause_categories():
    """TASK-COH-LLM-APPLIC-009: LLM rules only evaluate clauses whose inferred
    category matches the rule's category (mirrors deterministic applicability).
    The legal rule must NOT fire on a budget clause; LEGAL stays assessed via a
    real legal clause; the budget clause still gets its own (budget) rule."""
    from src.coherence.graph.nodes import llm_semantic_evaluate_async

    budget_clause = Clause(
        id="budget-1",
        text="Unit price and total amount payment for the contingency line item.",
        data={"document_type": "budget", "category": "BUDGET"},
    )
    legal_clause = Clause(
        id="legal-1",
        text="This contract clause assigns liability and penalty; termination "
             "requires notice and disputes are resolved by arbitration.",
        data={"document_type": "contract", "category": "LEGAL"},
    )
    state = CoherenceGraphState(
        project_id="p", clauses=[budget_clause, legal_clause],
        config=EvaluationConfig(tenant_id="00000000-0000-0000-0000-000000000001"),
    )

    gate = RecordingGate()
    out = await llm_semantic_evaluate_async(state, gate=gate)

    called = set(gate.calls)
    # The over-flagging bug: legal rule must NOT run on a budget clause.
    assert ("R-RESPONSIBILITY-01", "budget-1") not in called
    # LEGAL must remain assessed → legal rule runs on the real legal clause.
    assert ("R-RESPONSIBILITY-01", "legal-1") in called
    assert out["coverage_map"]["LEGAL"] is True
    # No over-skipping: the budget clause still gets its own rule.
    assert ("R-PAYMENT-CLARITY-01", "budget-1") in called
    # Gating actually pruned irrelevant (clause, rule) pairs.
    assert out["llm_skipped_count"] > 0
    assert len(called) < len(state.clauses) * len(_RULE_CATEGORY)


@pytest.mark.asyncio
async def test_run_gate_skips_non_substantive_clauses_before_llm_call():
    """TASK-COH-LLM-APPLIC-009-P3: headings and structured BOM rows are not
    substantive legal/payment clauses, so they must not consume LLM calls."""
    from src.coherence.graph.nodes import llm_semantic_evaluate_async

    heading_clause = Clause(
        id="legal-heading",
        text="Appendix 3 Insurance Requirements",
        data={"document_type": "contract", "category": "LEGAL"},
    )
    budget_line_clause = Clause(
        id="bom-1",
        text="1.1 Personal PMO, site manager, administrativo",
        data={
            "document_type": "budget",
            "category": "BUDGET",
            "source": "procurement_bom",
            "unit_price": 100.0,
            "quantity": 2.0,
            "line_total": 200.0,
        },
    )
    certificate_clause = Clause(
        id="legal-certificate",
        text="Manufacturer's / suppliers warranty certificate.",
        data={"document_type": "contract", "category": "LEGAL"},
    )
    appendix_list_clause = Clause(
        id="legal-appendix-list",
        text=(
            "Approved Subcontractors\n"
            "Appendix 6 Scope of Works and Supply by the Employer\n"
            "Appendix 7 List of Documents for Approval or Review\n"
            "Appendix 8 Functional Guarantees"
        ),
        data={"document_type": "contract", "category": "LEGAL"},
    )
    substantive_clause = Clause(
        id="legal-obligation",
        text=(
            "This contract clause assigns liability, penalty, notice and "
            "arbitration duties, but the parties will collaborate without "
            "specifying which party shall maintain the insurance."
        ),
        data={"document_type": "contract", "category": "LEGAL"},
    )
    state = CoherenceGraphState(
        project_id="p",
        clauses=[
            heading_clause,
            budget_line_clause,
            certificate_clause,
            appendix_list_clause,
            substantive_clause,
        ],
        config=EvaluationConfig(tenant_id="00000000-0000-0000-0000-000000000001"),
    )

    gate = RecordingGate()
    out = await llm_semantic_evaluate_async(state, gate=gate)

    called = set(gate.calls)
    assert ("R-RESPONSIBILITY-01", "legal-heading") not in called
    assert ("R-PAYMENT-CLARITY-01", "bom-1") not in called
    assert ("R-RESPONSIBILITY-01", "legal-certificate") not in called
    assert ("R-RESPONSIBILITY-01", "legal-appendix-list") not in called
    assert ("R-RESPONSIBILITY-01", "legal-obligation") in called
    assert out["skipped_non_substantive_count"] == 4
    assert out["llm_calls_count"] == 1


@pytest.mark.asyncio
async def test_run_gate_applicability_logs_render_with_stdlib_logger(caplog):
    """TASK-COH-LLM-APPLIC-009-P3: applicability logs render as grep-friendly
    stdlib log messages when INFO/DEBUG logging is enabled."""
    from src.coherence.graph.nodes import llm_semantic_evaluate_async

    heading_clause = Clause(
        id="legal-heading",
        text="Appendix 3 Insurance Requirements",
        data={"document_type": "contract", "category": "LEGAL"},
    )
    budget_clause = Clause(
        id="budget-1",
        text="Payment amount and unit price are defined for the line item.",
        data={"document_type": "budget", "category": "BUDGET"},
    )
    state = CoherenceGraphState(
        project_id="p",
        clauses=[heading_clause, budget_clause],
        config=EvaluationConfig(tenant_id="00000000-0000-0000-0000-000000000001"),
    )

    gate = RecordingGate()
    with caplog.at_level(logging.DEBUG, logger="src.coherence.graph.nodes"):
        out = await llm_semantic_evaluate_async(state, gate=gate)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert out["llm_calls_count"] == 1
    assert "coherence_llm_gate.skipped_non_substantive" in messages
    assert "clause_id=legal-heading" in messages
    assert "coherence_llm_gate.skipped_not_applicable" in messages
    assert "rule_id=R-SCOPE-CLARITY-01" in messages
    assert "coherence_llm_gate.applicability_summary" in messages
    assert "clauses=2" in messages
    assert "evaluated=1" in messages
    assert "skipped_not_applicable=5" in messages
    assert "skipped_non_substantive=1" in messages
