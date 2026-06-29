"""TS-COH-ASYNC-GRAPH-001: async coherence graph entrypoint regressions."""

from __future__ import annotations

import asyncio
import inspect
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.coherence.domain.ports.coherence_llm_gate_port import GateDecision
from src.coherence.graph import graph as graph_module
from src.coherence.graph import nodes as nodes_module
from src.coherence.graph.state import ClauseWithEmbedding, EvaluationConfig
from src.coherence.models import Clause, EnrichedCoherenceResult, FindingSignal


@pytest.fixture(autouse=True)
def _reset_compiled_graph_cache():
    original_graph = graph_module._compiled_graph
    graph_module._compiled_graph = None
    yield
    graph_module._compiled_graph = original_graph


def _registered_callable(state_graph, node_name: str):
    runnable = state_graph.nodes[node_name].runnable
    return runnable.func or runnable.afunc


def _disable_langsmith_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    from langchain_core.tracers import context as langchain_tracing_context
    from langsmith import run_helpers as langsmith_run_helpers
    from langsmith import utils as langsmith_utils

    @contextmanager
    def _disabled_tracing_v2(*_args: object, **_kwargs: object):
        yield None

    monkeypatch.setattr(
        langsmith_run_helpers,
        "get_tracing_context",
        lambda: {"parent": None, "project_name": None, "enabled": False},
    )
    monkeypatch.setattr(langsmith_utils, "tracing_is_enabled", lambda: False)
    monkeypatch.setattr(
        langchain_tracing_context,
        "_tracing_v2_is_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        langchain_tracing_context,
        "tracing_v2_enabled",
        _disabled_tracing_v2,
    )
    monkeypatch.setattr(
        "langchain_core.callbacks.manager._get_tracer_project",
        lambda *_a, **_k: "default",
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_core.tracers.context._get_tracer_project",
        lambda *_a, **_k: "default",
        raising=False,
    )


def _finding(rule_id: str, clause_id: str, category: str) -> FindingSignal:
    return FindingSignal(
        rule_id=rule_id,
        clause_id=clause_id,
        source="llm",
        impact_score=0.5,
        confidence=0.9,
        severity="medium",
        category=category,
        evidence_summary="fake finding",
        quote="fake quote",
    )


class CategoryConfinedGate:
    """Fake async gate that returns findings only for category-matched rules."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def evaluate_rule(self, tenant_id: str, rule_id: str, clause: Clause):
        self.calls.append((rule_id, clause.id))
        category = {
            "R-PAYMENT-CLARITY-01": "BUDGET",
            "R-RESPONSIBILITY-01": "LEGAL",
        }.get(rule_id)
        return GateDecision(
            state="evaluated",
            finding=_finding(rule_id, clause.id, category) if category else None,
            reason=None,
            reset_date=None,
            cache_key=f"{rule_id}:{clause.id}",
            cost_charged_usd=0.0,
        )


def test_graphs_register_async_llm_and_rag_nodes():
    graph = graph_module.build_coherence_subgraph()
    parallel_graph = graph_module.build_parallel_coherence_subgraph()

    for state_graph in (graph, parallel_graph):
        assert inspect.iscoroutinefunction(
            _registered_callable(state_graph, "llm_semantic_evaluate")
        )
        assert inspect.iscoroutinefunction(
            _registered_callable(state_graph, "rag_similarity_check")
        )


def test_async_entrypoint_seeds_router_coverage_like_sync_path(monkeypatch):
    expected_coverage = {"LEGAL": True, "BUDGET": True}
    captured: list[dict[str, bool]] = []

    class FakeGraph:
        async def ainvoke(self, state):
            captured.append(dict(state.coverage_map))
            return {"result": EnrichedCoherenceResult(overall_score=90.0)}

    monkeypatch.setattr(
        graph_module,
        "_seed_coverage_from_category_router",
        lambda clauses: dict(expected_coverage),
    )
    monkeypatch.setattr(graph_module, "get_coherence_subgraph", lambda: FakeGraph())

    clauses = [Clause(id="legal-1", text="The contract assigns liability.")]

    graph_module.evaluate_coherence(clauses, project_id="p", config=EvaluationConfig())
    asyncio.run(
        graph_module.evaluate_coherence_async(
            clauses,
            project_id="p",
            config=EvaluationConfig(),
        )
    )

    assert captured == [expected_coverage, expected_coverage]


@pytest.mark.asyncio
async def test_async_graph_llm_node_uses_main_loop_with_category_confined_gate(
    monkeypatch,
):
    _disable_langsmith_tracing(monkeypatch)
    main_thread = threading.get_ident()
    main_loop = asyncio.get_running_loop()
    observed: list[tuple[int, asyncio.AbstractEventLoop]] = []
    gate = CategoryConfinedGate()

    legal_clause = Clause(
        id="legal-1",
        text="The contractor shall maintain insurance and assign liability.",
        data={"category": "LEGAL", "document_type": "contract"},
    )
    budget_clause = Clause(
        id="budget-1",
        text="Payment amount and unit price are defined for the line item.",
        data={"category": "BUDGET", "document_type": "budget"},
    )

    def fake_prepare_context(state):
        return {
            "enriched_clauses": [
                ClauseWithEmbedding(clause=legal_clause, category="LEGAL"),
                ClauseWithEmbedding(clause=budget_clause, category="BUDGET"),
            ]
        }

    async def fake_llm_node(state):
        observed.append((threading.get_ident(), asyncio.get_running_loop()))
        return await nodes_module.llm_semantic_evaluate_async(state, gate=gate)

    def empty_node(state):
        return {}

    async def empty_async_node(state):
        return {}

    def fake_scoring(state):
        return {
            "all_signals": list(state.llm_signals),
            "score": 80.0,
            "diagnostics": {},
        }

    def fake_format(state):
        return {
            "result": EnrichedCoherenceResult(
                overall_score=80.0,
                finding_signals=list(state.all_signals),
                llm_findings_count=len(state.llm_signals),
                deterministic_findings_count=0,
            )
        }

    monkeypatch.setattr(graph_module, "prepare_context", fake_prepare_context)
    monkeypatch.setattr(graph_module, "deterministic_evaluate", empty_node)
    monkeypatch.setattr(graph_module, "llm_semantic_evaluate_async", fake_llm_node)
    monkeypatch.setattr(graph_module, "rag_similarity_check_async", empty_async_node)
    monkeypatch.setattr(graph_module, "cross_clause_eval", empty_node)
    monkeypatch.setattr(graph_module, "scoring_arbiter", fake_scoring)
    monkeypatch.setattr(graph_module, "format_output", fake_format)

    result = await graph_module.evaluate_coherence_async(
        clauses=[legal_clause, budget_clause],
        project_id="p",
        config=EvaluationConfig(
            low_budget_mode=False,
            include_rag_similarity=True,
            tenant_id=str(uuid4()),
        ),
    )

    assert observed == [(main_thread, main_loop)]
    findings_by_clause = {
        signal.clause_id: signal for signal in result.finding_signals
        if signal.rule_id.startswith("R-")
    }
    assert findings_by_clause["legal-1"].rule_id == "R-RESPONSIBILITY-01"
    assert findings_by_clause["legal-1"].category == "LEGAL"
    assert findings_by_clause["budget-1"].rule_id == "R-PAYMENT-CLARITY-01"
    assert findings_by_clause["budget-1"].category == "BUDGET"
    assert ("R-RESPONSIBILITY-01", "budget-1") not in gate.calls
    assert ("R-PAYMENT-CLARITY-01", "legal-1") not in gate.calls


@pytest.mark.asyncio
async def test_router_awaits_async_coherence_entrypoint(monkeypatch):
    from src.coherence import router as router_module

    called: list[tuple[list[Clause], str]] = []

    def sync_entrypoint_should_not_run(*args, **kwargs):
        raise AssertionError("router used sync evaluate_coherence")

    async def fake_async_entrypoint(*, clauses, project_id, config):
        called.append((clauses, project_id))
        assert config.low_budget_mode is False
        return EnrichedCoherenceResult(overall_score=88.0)

    monkeypatch.setattr(
        router_module,
        "evaluate_coherence",
        sync_entrypoint_should_not_run,
        raising=False,
    )
    monkeypatch.setattr(
        router_module,
        "evaluate_coherence_async",
        fake_async_entrypoint,
        raising=False,
    )

    clause = Clause(id="manual-1", text="The contractor shall maintain insurance.")
    payload = router_module.CoherenceEvaluateRequest(
        clauses=[clause],
        low_budget_mode=False,
        include_rag_similarity=True,
    )
    user = SimpleNamespace(tenant_id=uuid4())

    result = await router_module.evaluate_project_coherence(
        payload=payload,
        include_diagnostics=True,
        db=SimpleNamespace(),
        current_user=user,
    )

    assert result.overall_score == pytest.approx(88.0)
    assert called == [([clause], "manual")]
