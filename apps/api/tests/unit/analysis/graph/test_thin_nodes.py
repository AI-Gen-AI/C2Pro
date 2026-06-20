"""Thin-node delegation tests for the decoupled LangGraph nodes.

These tests prove that:
  * Each node only reads/writes state and delegates to a use case.
  * The node does not contain inline AI prompts or business math.

Dependency injection is performed via `monkeypatch` on
`src.analysis.adapters.graph.dependencies.get_ai_service` so no real
Anthropic wrapper is constructed.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 3 coverage gate.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from src.analysis.adapters.graph.schema import ProjectState
from src.modules.hitl.domain.entities import ReviewStatus


class _FakeAI:
    def __init__(self, payload: Any | None = None, raises: Exception | None = None) -> None:
        self._payload = payload
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        self.calls.append((system_prompt, user_content))
        if self._raises:
            raise self._raises
        return self._payload


def _make_state(**overrides) -> ProjectState:
    defaults: dict = {
        "project_id": "00000000-0000-0000-0000-000000000001",
        "document_id": "00000000-0000-0000-0000-000000000002",
        "document_text": "sample",
        "doc_type": "",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "tenant_id": "00000000-0000-0000-0000-000000000099",
        "analysis_id": None,
        "human_approval_required": False,
        "document_parsed": False,
        "document_category": "",
        "anonymized_text": "",
        "pii_redactions": [],
        "extracted_stakeholders": [],
        "raci_matrix": [],
        "coherence_score": 0,
        "coherence_breakdown": {},
        "bom_items": [],
        "knowledge_graph_nodes": [],
        "knowledge_graph_edges": [],
        "decision_package": {},
        "citations": [],
        "citation_validation_passed": False,
        "final_report": {},
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


class _AsyncContext:
    def __init__(self, value: Any = object()) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakeHitlService:
    def __init__(self, status: ReviewStatus) -> None:
        self.status = status
        self.calls: list[dict[str, Any]] = []

    async def route_for_review(self, **kwargs: Any) -> ReviewStatus:
        self.calls.append(kwargs)
        return self.status


# ── N3 router_node ──────────────────────────────────────────────────────────


class TestRouterNodeThinDelegation:
    @pytest.mark.asyncio
    async def test_uses_existing_doc_type_when_valid(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        # get_ai_service must not even be constructed for the short-circuit path.
        def _explode(*_a, **_kw):
            raise AssertionError("get_ai_service called on short-circuit path")
        monkeypatch.setattr(nodes, "get_ai_service", _explode, raising=False)

        state = _make_state(doc_type="contract")
        msg_count_before = len(state["messages"])
        result = await nodes.router_node(state)
        assert result["doc_type"] == "contract"
        # Parity with original: short-circuit adds no new message.
        assert len(result["messages"]) == msg_count_before

    @pytest.mark.asyncio
    async def test_delegates_to_use_case_when_unknown(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        ai = _FakeAI(payload={"doc_type": "budget"})
        monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai, raising=False)

        result = await nodes.router_node(_make_state(document_text="capex totals"))
        assert result["doc_type"] == "budget"
        assert len(ai.calls) == 1

    @pytest.mark.asyncio
    async def test_falls_back_via_use_case(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        ai = _FakeAI(raises=RuntimeError())
        monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai, raising=False)

        result = await nodes.router_node(_make_state(document_text="contract clauses"))
        assert result["doc_type"] == "contract"


# ── N12 critique_node ───────────────────────────────────────────────────────


class TestCritiqueNodeThinDelegation:
    @pytest.mark.asyncio
    async def test_ok_path(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        ai = _FakeAI(payload={"status": "OK", "notes": ""})
        monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai, raising=False)

        result = await nodes.critique_node(
            _make_state(extracted_risks=[{"confidence": 0.9}])
        )
        assert result["human_approval_required"] is False
        assert result["confidence_score"] == pytest.approx(0.9)
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_retry_path_increments(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        ai = _FakeAI(payload={"status": "RETRY", "notes": "redo"})
        monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai, raising=False)

        result = await nodes.critique_node(
            _make_state(extracted_risks=[{"confidence": 0.9}], retry_count=0)
        )
        assert result["retry_count"] == 1
        assert result["critique_notes"] == "redo"

    @pytest.mark.asyncio
    async def test_mock_mode_short_circuits(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
        # AIService must NOT be touched in mock mode
        def _explode(*_a, **_kw):
            raise AssertionError("get_ai_service called in mock mode")
        monkeypatch.setattr(nodes, "get_ai_service", _explode, raising=False)

        result = await nodes.critique_node(_make_state())
        assert result["confidence_score"] == 0.95
        assert result["human_approval_required"] is False


# ── N4/N5 deterministic helper shims ────────────────────────────────────────


class TestDeterministicShims:
    def test_deterministic_contract_risks(self) -> None:
        from src.analysis.adapters.graph import nodes

        risks = nodes._deterministic_contract_risks("penalty 2% for delay")
        assert risks and risks[0]["category"] == "LEGAL"

    def test_deterministic_wbs_items(self) -> None:
        from src.analysis.adapters.graph import nodes

        items = nodes._deterministic_wbs_items("scope with deadline")
        assert {i["code"] for i in items} == {"1.1", "1.2"}

    @pytest.mark.asyncio
    async def test_classify_doc_type_shim(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        ai = _FakeAI(payload={"doc_type": "schedule"})
        monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai, raising=False)
        assert await nodes._classify_doc_type("text", "tenant") == "schedule"


# ── N4 mock branch ──────────────────────────────────────────────────────────


class TestRiskExtractorMockBranch:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_honest_empty_risks(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
        result = await nodes.risk_extractor_node(
            _make_state(document_text="penalty for delay")
        )
        assert result["extracted_risks"] == []

    @pytest.mark.asyncio
    async def test_mock_mode_does_not_fabricate_risks(self, monkeypatch) -> None:
        """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
        from src.analysis.adapters.graph import nodes

        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
        result = await nodes.risk_extractor_node(
            _make_state(document_text="penalty for delay", confidence_score=0.2)
        )

        assert result["extracted_risks"] == []
        assert result["confidence_score"] == pytest.approx(0.2)
        assert any(
            "mock mode" in message.content.lower()
            and "no risks extracted" in message.content.lower()
            for message in result["messages"]
        )


class TestWbsExtractorMockBranch:
    @pytest.mark.asyncio
    async def test_mock_mode_uses_deterministic_rules(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
        result = await nodes.wbs_extractor_node(
            _make_state(document_text="scope with deadline")
        )
        assert len(result["extracted_wbs"]) == 2


class TestHumanInterruptNode:
    @pytest.mark.asyncio
    async def test_auto_approved_hitl_status_continues_without_langgraph_interrupt(
        self, monkeypatch
    ) -> None:
        """Test Suite ID: TS-QA-SWAGGER-ANALYSIS-002."""
        from src.analysis.adapters.graph import nodes

        service = _FakeHitlService(ReviewStatus.APPROVED)
        monkeypatch.setattr(
            nodes,
            "get_session_with_tenant",
            lambda tenant_id: _AsyncContext(value={"tenant_id": tenant_id}),
            raising=False,
        )
        monkeypatch.setattr(
            nodes,
            "get_hitl_service_for_graph",
            lambda *, session, tenant_id: service,
            raising=False,
        )

        def _interrupt_must_not_be_called(payload: dict[str, Any]) -> None:
            raise AssertionError(f"unexpected interrupt: {payload}")

        monkeypatch.setattr(nodes, "interrupt", _interrupt_must_not_be_called)

        result = await nodes.human_interrupt_node(
            _make_state(
                doc_type="contract",
                confidence_score=0.9,
                retry_count=2,
                thread_id="thread-swagger-analysis",
            )
        )

        assert result["human_approval_required"] is False
        assert service.calls[0]["item_id"] == UUID(result["document_id"])
        assert service.calls[0]["item_data"]["thread_id"] == "thread-swagger-analysis"
        assert service.calls[0]["metadata"]["thread_id"] == "thread-swagger-analysis"


# ── N7 raci_generator_node ──────────────────────────────────────────────────


class TestRaciGeneratorNodeDelegation:
    @pytest.mark.asyncio
    async def test_delegates_to_use_case(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended

        ai = _FakeAI(payload=[{"task": "T1", "role": "R"}])
        monkeypatch.setattr(
            nodes_extended, "get_ai_service", lambda tenant_id: ai, raising=False
        )

        result = await nodes_extended.raci_generator_node(
            _make_state(
                extracted_stakeholders=[{"name": "A"}],
                extracted_wbs=[{"code": "1.1"}],
            )
        )
        assert result["raci_matrix"] == [{"task": "T1", "role": "R"}]
        assert len(ai.calls) == 1

    @pytest.mark.asyncio
    async def test_ai_failure_returns_empty(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended

        ai = _FakeAI(raises=RuntimeError())
        monkeypatch.setattr(
            nodes_extended, "get_ai_service", lambda tenant_id: ai, raising=False
        )
        result = await nodes_extended.raci_generator_node(
            _make_state(
                extracted_stakeholders=[{"name": "A"}],
                extracted_wbs=[{"code": "1.1"}],
            )
        )
        assert result["raci_matrix"] == []


# ── N9 budget_parser_extended_node ──────────────────────────────────────────


class TestBudgetParserExtendedNodeDelegation:
    @pytest.mark.asyncio
    async def test_sets_bom_items_and_confidence(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended

        ai = _FakeAI(payload={"items": [{"name": "Steel", "amount": 100.0}]})
        monkeypatch.setattr(
            nodes_extended, "get_ai_service", lambda tenant_id: ai, raising=False
        )

        result = await nodes_extended.budget_parser_extended_node(
            _make_state(document_text="budget", anonymized_text="")
        )
        assert len(result["bom_items"]) == 1
        assert result["confidence_score"] == 0.7

    @pytest.mark.asyncio
    async def test_empty_items_zero_confidence(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended

        ai = _FakeAI(payload={"items": []})
        monkeypatch.setattr(
            nodes_extended, "get_ai_service", lambda tenant_id: ai, raising=False
        )
        result = await nodes_extended.budget_parser_extended_node(
            _make_state(document_text="budget")
        )
        assert result["bom_items"] == []
        assert result["confidence_score"] == 0.0

    @pytest.mark.asyncio
    async def test_prefers_anonymized_text(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended

        ai = _FakeAI(payload={"items": [{"name": "X"}]})
        monkeypatch.setattr(
            nodes_extended, "get_ai_service", lambda tenant_id: ai, raising=False
        )
        await nodes_extended.budget_parser_extended_node(
            _make_state(document_text="orig", anonymized_text="anon version")
        )
        # AI received anonymized text, not original
        assert ai.calls[0][1] == "anon version"


# ── Phase 4: conditional edge routing ───────────────────────────────────────


class TestCritiqueRouter:
    def test_hitl_path(self) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        assert (
            _next_after_critique_v2(_make_state(human_approval_required=True))
            == "human_interrupt"
        )

    def test_retry_contract_branch(self) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        assert (
            _next_after_critique_v2(
                _make_state(critique_notes="x", retry_count=1, doc_type="contract")
            )
            == "risk_extractor"
        )

    def test_retry_budget_branch(self) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        assert (
            _next_after_critique_v2(
                _make_state(critique_notes="x", retry_count=1, doc_type="budget")
            )
            == "budget_parser"
        )

    def test_retry_default_branch(self) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        assert (
            _next_after_critique_v2(
                _make_state(critique_notes="x", retry_count=1, doc_type="technical_spec")
            )
            == "wbs_extractor"
        )

    def test_ok_proceeds_to_enrichment(self) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        assert _next_after_critique_v2(_make_state()) == "stakeholder_extractor"

    def test_mock_mode_skips_hitl(self, monkeypatch) -> None:
        from src.analysis.adapters.graph.workflow import _next_after_critique_v2

        monkeypatch.setenv("C2PRO_AI_MOCK", "1")
        assert (
            _next_after_critique_v2(_make_state(human_approval_required=True))
            == "stakeholder_extractor"
        )


# ── N17 save_to_db_node short-circuit ───────────────────────────────────────


class TestSaveToDbNodeShortCircuit:
    @pytest.mark.asyncio
    async def test_skips_without_tenant(self) -> None:
        from src.analysis.adapters.graph import nodes

        result = await nodes.save_to_db_node(_make_state(tenant_id=None))
        assert result.get("analysis_id") is None


# ── N4 / N5 non-mock delegation to tool registry ────────────────────────────


class TestExtractorAIToolDelegation:
    @pytest.mark.asyncio
    async def test_risk_extractor_uses_tool_registry(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)

        async def _fake_tool(state):
            state["extracted_risks"] = [{"title": "T"}]
            return state

        def _fake_get_tool(name, *, version):
            assert (name, version) == ("risk_extraction", "1.0")
            return _fake_tool

        # Patch the lazy import site.
        import sys
        import types
        fake_mod = types.ModuleType("src.core.ai.tools")
        fake_mod.get_tool = _fake_get_tool
        monkeypatch.setitem(sys.modules, "src.core.ai.tools", fake_mod)

        result = await nodes.risk_extractor_node(_make_state(document_text="real text"))
        assert result["extracted_risks"] == [{"title": "T"}]

    @pytest.mark.asyncio
    async def test_risk_extractor_tool_failure_returns_honest_empty_result(
        self, monkeypatch
    ) -> None:
        """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
        from src.analysis.adapters.graph import nodes

        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)

        async def _failing_tool(_state):
            raise RuntimeError("JSON parse failed at char 12: invalid schema")

        def _fake_get_tool(name, *, version):
            assert (name, version) == ("risk_extraction", "1.0")
            return _failing_tool

        import sys
        import types

        fake_mod = types.ModuleType("src.core.ai.tools")
        fake_mod.get_tool = _fake_get_tool
        monkeypatch.setitem(sys.modules, "src.core.ai.tools", fake_mod)

        result = await nodes.risk_extractor_node(
            _make_state(document_text="real text", confidence_score=0.33)
        )

        assert result["extracted_risks"] == []
        assert result["confidence_score"] == pytest.approx(0.33)
        assert any(
            "RuntimeError" in message.content
            and "JSON parse failed" in message.content
            for message in result["messages"]
        )

    @pytest.mark.asyncio
    async def test_risk_extractor_tool_empty_returns_honest_degraded_result(
        self, monkeypatch
    ) -> None:
        """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
        from src.analysis.adapters.graph import nodes

        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)

        async def _empty_tool(state):
            state["extracted_risks"] = []
            state["confidence_score"] = 0.7
            return state

        def _fake_get_tool(name, *, version):
            assert (name, version) == ("risk_extraction", "1.0")
            return _empty_tool

        import sys
        import types

        fake_mod = types.ModuleType("src.core.ai.tools")
        fake_mod.get_tool = _fake_get_tool
        monkeypatch.setitem(sys.modules, "src.core.ai.tools", fake_mod)

        result = await nodes.risk_extractor_node(
            _make_state(document_text="real text", confidence_score=0.25)
        )

        assert result["extracted_risks"] == []
        assert result["confidence_score"] == pytest.approx(0.25)
        assert any(
            "AI risk extraction failed/empty" in message.content
            for message in result["messages"]
        )

    @pytest.mark.asyncio
    async def test_wbs_extractor_uses_tool_registry(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes

        monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)

        async def _fake_tool(state):
            state["extracted_wbs"] = [{"code": "W"}]
            return state

        def _fake_get_tool(name, *, version):
            assert (name, version) == ("wbs_extraction", "1.0")
            return _fake_tool

        import sys
        import types
        fake_mod = types.ModuleType("src.core.ai.tools")
        fake_mod.get_tool = _fake_get_tool
        monkeypatch.setitem(sys.modules, "src.core.ai.tools", fake_mod)

        result = await nodes.wbs_extractor_node(_make_state(document_text="real text"))
        assert result["extracted_wbs"] == [{"code": "W"}]

    @pytest.mark.asyncio
    async def test_budget_parser_delegates_to_extended(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes, nodes_extended

        ai = _FakeAI(payload={"items": [{"name": "Steel"}]})
        monkeypatch.setattr(
            nodes_extended, "get_ai_service", lambda tenant_id: ai, raising=False
        )
        result = await nodes.budget_parser_node(_make_state(document_text="budget"))
        assert len(result["bom_items"]) == 1
