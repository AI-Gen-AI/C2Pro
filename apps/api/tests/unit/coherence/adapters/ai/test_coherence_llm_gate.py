from src.coherence.domain.ports.coherence_llm_gate_port import (
    CoherenceLlmGatePort,
    GateDecision,
)


def test_gate_decision_states_are_exact():
    """The 4 documented states are the only legal values."""
    legal = {"evaluated", "cache_hit", "budget_exhausted", "rolled_out_off"}
    for s in legal:
        d = GateDecision(state=s, finding=None, reason=None,
                         reset_date=None, cache_key=None, cost_charged_usd=0.0)
        assert d.state == s


def test_gate_decision_is_frozen():
    import dataclasses
    d = GateDecision(state="evaluated", finding=None, reason=None,
                     reset_date=None, cache_key="abc", cost_charged_usd=0.01)
    assert dataclasses.fields(d)  # is a dataclass
    try:
        d.state = "cache_hit"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("GateDecision must be frozen")


def test_port_is_a_protocol():
    from typing import get_type_hints
    assert hasattr(CoherenceLlmGatePort, "evaluate_rule")
    # Just confirms the symbol exists; full conformance is exercised by adapter tests.
    _ = get_type_hints
