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
async def test_gate_evaluate_rule_returns_gate_decision_type(monkeypatch):
    """Post-Task-7: evaluate_rule returns a GateDecision through the full path."""
    from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
    from src.coherence.models import Clause
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")
    gate = CoherenceLlmGate()
    class _MissCache:
        async def get(self, key): return None
        async def set(self, key, value): pass
    class _OkCost:
        async def check_budget_availability(self, *a, **kw): return None
    class _NoopUsage:
        def record_usage(self, **kw): pass
    gate._cache = _MissCache()
    gate._cost = _OkCost()
    gate._usage = _NoopUsage()

    async def _fake_call(rule_id, clause):
        return None, 0, 0, 0.0, 1.0, "claude-3-haiku-20240307"
    monkeypatch.setattr(gate, "_call_rule_via_llm", _fake_call)

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001",
        "R-SCOPE-CLARITY-01",
        Clause(id="c", text="", data={}),
    )
    assert decision.state == "evaluated"
    assert decision.finding is None


PROMPT_VERSION_FOR_TESTS = "p3-v2"  # the canonical version the gate uses


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


@pytest.mark.asyncio
async def test_gate_cache_hit_applies_calibrated_thresholds():
    """TASK-COH-LLM-APPLIC-009-P3: stale cached weak findings must not bypass
    the calibrated LLM thresholds."""
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause, FindingSignal

    weak_cached_finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.15,
        confidence=0.95, severity="low", category="SCOPE",
        evidence_summary="weak cached", quote="q", raw_data={},
    )

    class FakeContentHashCache:
        async def get(self, key):
            return weak_cached_finding
        async def set(self, key, value):  # pragma: no cover - hit path
            raise AssertionError("cache set should not run on hit")

    class ExplodingCost:
        async def check_budget_availability(self, *a, **kw):
            raise AssertionError("budget should not run on cache hit")

    gate = g.CoherenceLlmGate()
    gate._cache = FakeContentHashCache()
    gate._cost = ExplodingCost()

    decision = await gate.evaluate_rule(
        "tenant-1", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="The scope is to design a substation.", data={}),
    )

    assert decision.state == "cache_hit"
    assert decision.finding is None
    assert decision.cost_charged_usd == 0.0


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


@pytest.mark.asyncio
async def test_gate_rolled_out_off_when_rule_pct_is_zero(monkeypatch):
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "0")

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value): pass

    cost_consulted = {"called": False}
    class FakeCost:
        async def check_budget_availability(self, *a, **kw):
            cost_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = EmptyCache()
    gate._cost = FakeCost()

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="any text", data={}),
    )

    assert decision.state == "rolled_out_off"
    assert decision.finding is None
    assert decision.reason == "rule_rollout_disabled"
    assert decision.cost_charged_usd == 0.0
    assert decision.cache_key is not None  # still computed
    assert cost_consulted["called"] is False  # critical: budget NOT consulted on rollout deny


@pytest.mark.asyncio
async def test_gate_budget_exhausted_returns_distinct_state_with_reset_date(monkeypatch):
    import datetime

    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause
    from src.core.ai.cost_controller import BudgetExceededException

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value): pass

    class FakeCost:
        async def check_budget_availability(self, tenant_uuid, estimated_cost):
            raise BudgetExceededException("test: budget exhausted")

    llm_consulted = {"called": False}
    class FakeLlm:
        async def call(self, *a, **kw):
            llm_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = EmptyCache()
    gate._cost = FakeCost()
    gate._llm = FakeLlm()

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="any text", data={}),
    )

    assert decision.state == "budget_exhausted"
    assert decision.reason == "tenant_budget_exhausted"
    # reset_date = first of next calendar month (matches cost_controller's monthly reset)
    today = datetime.date.today()
    expected = (
        datetime.date(today.year + 1, 1, 1) if today.month == 12
        else datetime.date(today.year, today.month + 1, 1)
    )
    assert decision.reset_date == expected
    assert decision.cost_charged_usd == 0.0
    assert llm_consulted["called"] is False  # LLM NOT consulted on exhausted


@pytest.mark.asyncio
async def test_gate_invalid_tenant_id_fails_closed_to_budget_exhausted(monkeypatch):
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value): pass

    cost_consulted = {"called": False}
    class FakeCost:
        async def check_budget_availability(self, *a, **kw):
            cost_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = EmptyCache()
    gate._cost = FakeCost()

    decision = await gate.evaluate_rule(
        "not-a-uuid", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="any text", data={}),
    )

    assert decision.state == "budget_exhausted"
    assert decision.reason == "invalid_tenant_id"
    assert cost_consulted["called"] is False  # short-circuited before cost call


@pytest.mark.asyncio
async def test_gate_evaluated_path_calls_llm_caches_result_and_charges(monkeypatch):
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause, FindingSignal

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    saved: dict[str, FindingSignal] = {}
    class FakeContentHashCache:
        async def get(self, key): return None
        async def set(self, key, value): saved[key] = value

    class FakeCost:
        async def check_budget_availability(self, *a, **kw): pass  # ok

    recorded: list[dict] = []
    class FakeUsage:
        def record_usage(self, *, model, task_name, input_tokens, output_tokens,
                          cost_usd, latency_ms, success, tenant_id=None, **_kw):
            recorded.append({
                "model": model, "task_name": task_name,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": cost_usd, "tenant_id": tenant_id,
                "latency_ms": latency_ms, "success": success,
            })

    finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.42,
        confidence=0.9, severity="medium", category="SCOPE",
        evidence_summary="ambiguous", quote="q", raw_data={},
    )

    # Inject the LLM-call helper directly so the test doesn't touch the real registry.
    # Helper returns (finding, input_tokens, output_tokens, cost, latency_ms, model).
    async def fake_call_rule(rule_id, clause):
        return finding, 120, 80, 0.0007, 250.0, "claude-3-haiku-20240307"

    gate = g.CoherenceLlmGate()
    gate._cache = FakeContentHashCache()
    gate._cost = FakeCost()
    gate._usage = FakeUsage()
    monkeypatch.setattr(gate, "_call_rule_via_llm", fake_call_rule)

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="ambiguous scope text", data={}),
    )

    assert decision.state == "evaluated"
    assert decision.finding is finding
    assert decision.cost_charged_usd == 0.0007
    assert decision.cache_key in saved and saved[decision.cache_key] is finding
    assert len(recorded) == 1
    r = recorded[0]
    assert r["model"] == "claude-3-haiku-20240307"
    assert r["task_name"] == "coherence_R-SCOPE-CLARITY-01"
    assert r["input_tokens"] == 120 and r["output_tokens"] == 80
    assert r["cost_usd"] == 0.0007
    assert r["tenant_id"] == "00000000-0000-0000-0000-000000000001"
    assert r["success"] is True


@pytest.mark.asyncio
async def test_gate_llm_error_does_not_charge_or_cache(monkeypatch):
    """If the LLM call raises, we must NOT charge usage_analytics nor cache anything.
    The exception propagates up — node converts to errors[] + SKIPPED for the rule."""
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    saved: dict = {}
    class FakeContentHashCache:
        async def get(self, key): return None
        async def set(self, key, value): saved[key] = value

    class FakeCost:
        async def check_budget_availability(self, *a, **kw): pass

    recorded: list = []
    class FakeUsage:
        def record_usage(self, **kw):
            recorded.append(kw)

    async def boom(rule_id, clause):
        raise RuntimeError("upstream LLM 5xx")

    gate = g.CoherenceLlmGate()
    gate._cache = FakeContentHashCache()
    gate._cost = FakeCost()
    gate._usage = FakeUsage()
    monkeypatch.setattr(gate, "_call_rule_via_llm", boom)

    with pytest.raises(RuntimeError):
        await gate.evaluate_rule(
            "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
            Clause(id="c1", text="x", data={}),
        )
    assert saved == {}
    assert recorded == []


@pytest.mark.asyncio
async def test_gate_none_finding_recorded_as_failure_not_success(monkeypatch):
    """v1 LlmRuleEvaluator swallows LLM 5xx and returns None; ensure that surfaces
    to usage_analytics as success=False, not a $0 successful call (telemetry honesty)."""
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    class EmptyCache:
        def __init__(self):
            self.set_calls = 0
        async def get(self, key): return None
        async def set(self, key, value):
            self.set_calls += 1

    class FakeCost:
        async def check_budget_availability(self, *a, **kw): pass

    recorded: list[dict] = []
    class FakeUsage:
        def record_usage(self, **kw):
            recorded.append(kw)

    async def fake_call_returning_none(rule_id, clause):
        return None, 0, 0, 0.0, 12.3, "claude-3-haiku-20240307"

    cache = EmptyCache()
    gate = g.CoherenceLlmGate()
    gate._cache = cache
    gate._cost = FakeCost()
    gate._usage = FakeUsage()
    monkeypatch.setattr(gate, "_call_rule_via_llm", fake_call_returning_none)

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="x", data={}),
    )

    # 1. Cache NOT written when finding is None (no poisoning).
    assert cache.set_calls == 0

    # 2. record_usage called with success=False on swallowed-error path.
    assert len(recorded) == 1
    assert recorded[0]["success"] is False
    assert recorded[0]["cost_usd"] == 0.0
    assert recorded[0]["input_tokens"] == 0
    assert recorded[0]["output_tokens"] == 0

    # 3. Decision is still "evaluated" (the evaluator didn't raise — gate
    #    only sees a None finding, which is a valid "no violation" outcome
    #    semantically), with finding=None.
    assert decision.state == "evaluated"
    assert decision.finding is None


@pytest.mark.asyncio
async def test_gate_drops_findings_below_calibrated_thresholds(monkeypatch):
    """TASK-COH-LLM-APPLIC-009-P3: the live gate path must apply the same
    impact/confidence thresholds as the v1 evaluator path."""
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause, FindingSignal

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    class EmptyCache:
        def __init__(self):
            self.set_calls = 0
        async def get(self, key): return None
        async def set(self, key, value):
            self.set_calls += 1

    class FakeCost:
        async def check_budget_availability(self, *a, **kw): pass

    recorded: list[dict] = []
    class FakeUsage:
        def record_usage(self, **kw):
            recorded.append(kw)

    weak_finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.15,
        confidence=0.95, severity="low", category="SCOPE",
        evidence_summary="weak", quote="q", raw_data={},
    )

    async def fake_call_rule(rule_id, clause):
        return weak_finding, 10, 5, 0.0001, 20.0, "claude-3-haiku-20240307"

    cache = EmptyCache()
    gate = g.CoherenceLlmGate()
    gate._cache = cache
    gate._cost = FakeCost()
    gate._usage = FakeUsage()
    monkeypatch.setattr(gate, "_call_rule_via_llm", fake_call_rule)

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001",
        "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="The contractor shall perform work as needed.", data={}),
    )

    assert decision.state == "evaluated"
    assert decision.finding is None
    assert cache.set_calls == 0
    assert recorded[0]["success"] is False


@pytest.mark.asyncio
async def test_gate_none_tenant_id_fails_closed_to_budget_exhausted(monkeypatch):
    """UUID(None) raises TypeError; gate must catch and fail-closed."""
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value): pass

    cost_consulted = {"called": False}
    class FakeCost:
        async def check_budget_availability(self, *a, **kw):
            cost_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = EmptyCache()
    gate._cost = FakeCost()

    decision = await gate.evaluate_rule(
        None,  # type: ignore[arg-type]
        "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="any text", data={}),
    )

    assert decision.state == "budget_exhausted"
    assert decision.reason == "invalid_tenant_id"
    assert cost_consulted["called"] is False
