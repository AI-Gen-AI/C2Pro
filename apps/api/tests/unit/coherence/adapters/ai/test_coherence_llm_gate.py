import pytest

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


def test_gate_constructs_with_lazy_deps():
    from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
    gate = CoherenceLlmGate()
    # Lazy: nothing resolved yet
    assert gate._cache is None
    assert gate._cost is None
    assert gate._router is None
    assert gate._usage is None
    assert gate._llm is None


@pytest.mark.asyncio
async def test_gate_evaluate_rule_returns_gate_decision_type():
    """Until Tasks 4-7 land, evaluate_rule is allowed to raise NotImplementedError —
    this test just pins the async signature."""
    from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
    from src.coherence.models import Clause
    gate = CoherenceLlmGate()
    # Cache-miss path still raises NotImplementedError until Tasks 5-7 land.
    class _MissCache:
        async def get(self, key): return None
        async def set(self, key, value): pass
    gate._cache = _MissCache()
    with pytest.raises(NotImplementedError):
        await gate.evaluate_rule("tenant", "R-SCOPE-CLARITY-01",
                                  Clause(id="c", text="", data={}))


PROMPT_VERSION_FOR_TESTS = "p3-v1"  # the canonical version the gate uses


@pytest.mark.asyncio
async def test_gate_returns_cache_hit_without_consulting_budget_or_llm():
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause, FindingSignal

    cached_finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.4,
        confidence=1.0, severity="medium", category="SCOPE",
        evidence_summary="cached", quote="q", raw_data={"source": "llm"},
    )

    class FakeContentHashCache:
        def __init__(self):
            self.get_calls = 0
            self.set_calls = 0
        async def get(self, key):
            self.get_calls += 1
            return cached_finding
        async def set(self, key, value):  # pragma: no cover — hit path
            self.set_calls += 1

    cost_consulted = {"called": False}
    class FakeCost:
        async def check_budget_availability(self, *a, **kw):
            cost_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = FakeContentHashCache()
    gate._cost = FakeCost()

    decision = await gate.evaluate_rule(
        "tenant-1", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="The scope is to design a substation.", data={}),
    )

    assert decision.state == "cache_hit"
    assert decision.finding is cached_finding
    assert decision.cost_charged_usd == 0.0
    assert decision.cache_key is not None and len(decision.cache_key) == 64  # sha256 hex
    assert cost_consulted["called"] is False  # critical: budget NOT consulted on hit
    assert gate._cache.get_calls == 1
    assert gate._cache.set_calls == 0


def test_content_hash_is_deterministic_and_canonicalized():
    from src.coherence.adapters.ai.coherence_llm_gate import _content_hash
    h1 = _content_hash("R-SCOPE-CLARITY-01", "  Some Text  ")
    h2 = _content_hash("R-SCOPE-CLARITY-01", "some text")
    assert h1 == h2, "canonicalization (strip + lower) must produce stable key"
    # Different rule_id → different key
    h3 = _content_hash("R-PAYMENT-CLARITY-01", "some text")
    assert h1 != h3


@pytest.mark.asyncio
async def test_content_hash_cache_roundtrips_finding_signal():
    from src.coherence.adapters.ai.content_hash_cache import ContentHashCache
    from src.coherence.models import FindingSignal

    class FakeCacheService:
        def __init__(self):
            self.store: dict[str, dict] = {}
        async def get_json(self, key):
            return self.store.get(key)
        async def set_json(self, key, value, ttl_seconds):
            self.store[key] = value

    svc = FakeCacheService()
    cache = ContentHashCache(svc)

    finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.42,
        confidence=0.9, severity="medium", category="SCOPE",
        evidence_summary="e", quote="q", raw_data={},
    )
    assert await cache.get("k1") is None  # miss
    await cache.set("k1", finding)
    got = await cache.get("k1")
    assert got is not None
    assert got.rule_id == finding.rule_id and got.impact_score == finding.impact_score


@pytest.mark.asyncio
async def test_content_hash_cache_returns_none_when_service_is_none():
    """When CacheService is unavailable (None), the wrapper degrades to a no-op."""
    from src.coherence.adapters.ai.content_hash_cache import ContentHashCache
    cache = ContentHashCache(cache_service=None)
    assert await cache.get("any") is None
    await cache.set("any", value=None)  # should not raise
