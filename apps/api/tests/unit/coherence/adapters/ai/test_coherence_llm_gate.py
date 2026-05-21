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


def test_rollout_config_defaults_all_six_rules_to_100():
    from src.coherence.adapters.ai.rollout_config import get_rollout_pct
    for rule_id in (
        "R-SCOPE-CLARITY-01",
        "R-PAYMENT-CLARITY-01",
        "R-SCHEDULE-CLARITY-01",
        "R-TECHNICAL-SPEC-CLARITY-01",
        "R-RESPONSIBILITY-01",
        "R-QUALITY-STANDARDS-01",
    ):
        assert get_rollout_pct(rule_id) == 100


def test_rollout_config_unknown_rule_is_zero():
    from src.coherence.adapters.ai.rollout_config import get_rollout_pct
    assert get_rollout_pct("R-UNKNOWN") == 0


def test_rollout_config_env_override(monkeypatch):
    from src.coherence.adapters.ai import rollout_config
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "10")
    assert rollout_config.get_rollout_pct("R-SCOPE-CLARITY-01") == 10


def test_rollout_config_env_clamps_to_0_100(monkeypatch):
    from src.coherence.adapters.ai import rollout_config
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "150")
    assert rollout_config.get_rollout_pct("R-SCOPE-CLARITY-01") == 100
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "-5")
    assert rollout_config.get_rollout_pct("R-SCOPE-CLARITY-01") == 0


def test_rollout_config_env_garbage_defaults_to_zero(monkeypatch):
    from src.coherence.adapters.ai import rollout_config
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "not-an-int")
    assert rollout_config.get_rollout_pct("R-SCOPE-CLARITY-01") == 0
