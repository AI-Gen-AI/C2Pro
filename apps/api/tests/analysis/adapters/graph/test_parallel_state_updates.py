"""
TS-UA-ANA-GRAPH-001 - Parallel analysis branch state update regression tests.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.analysis.adapters.graph.nodes_extended import (
    citation_validator_node,
    coherence_scorer_node,
    raci_generator_node,
    stakeholder_extractor_node,
)
from src.analysis.adapters.graph.workflow import compile_workflow, enrichment_dispatch_node


def _base_state() -> dict[str, object]:
    """TS-UA-ANA-GRAPH-001 - Build the smallest state needed by parallel graph branches."""
    return {
        "project_id": "project-1",
        "document_id": "document-1",
        "document_text": "Contract text with no specific clauses.",
        "anonymized_text": "",
        "doc_type": "contract",
        "tenant_id": None,
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "bom_items": [],
        "confidence_score": 0.9,
    }


@pytest.mark.asyncio
async def test_parallel_branches_return_only_branch_local_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-UA-ANA-GRAPH-001 - Parallel branches must not rewrite shared identity keys."""

    async def fake_evaluate_coherence_async(*_args: object, **_kwargs: object):
        class Result:
            overall_score = 88
            category_breakdown: list[object] = []
            score_reason = "ok"
            score_missing_dimensions: list[str] = []

        return Result()

    monkeypatch.setattr(
        "src.coherence.graph.graph.evaluate_coherence_async",
        fake_evaluate_coherence_async,
    )

    stakeholder_result = await stakeholder_extractor_node(_base_state())  # type: ignore[arg-type]
    raci_result = await raci_generator_node(_base_state())  # type: ignore[arg-type]
    coherence_result = await coherence_scorer_node(_base_state())  # type: ignore[arg-type]
    citation_result = await citation_validator_node(_base_state())  # type: ignore[arg-type]

    for result in (stakeholder_result, raci_result, coherence_result, citation_result):
        assert "project_id" not in result
        assert "document_id" not in result
        assert "tenant_id" not in result


@pytest.mark.asyncio
async def test_parallel_dispatch_does_not_rewrite_shared_identity_state() -> None:
    """TS-UA-ANA-GRAPH-001 - The fan-out anchor emits no full-state rewrite."""
    assert await enrichment_dispatch_node(_base_state()) == {}  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_compiled_workflow_merges_parallel_branches_without_rewriting_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UA-ANA-GRAPH-001 - The compiled fan-out must merge without duplicate identity writes."""
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
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
    monkeypatch.setattr(langchain_tracing_context, "_tracing_v2_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "tracing_v2_enabled", _disabled_tracing_v2)

    async def passthrough_document_ingestion(state: dict[str, object]) -> dict[str, object]:
        return {"document_parsed": True, "document_category": "LEGAL", "messages": []}

    async def passthrough_pii(state: dict[str, object]) -> dict[str, object]:
        return {"anonymized_text": state["document_text"], "pii_redactions": [], "messages": []}

    async def no_save(_state: dict[str, object]) -> dict[str, object]:
        return {"analysis_id": "analysis-1", "messages": []}

    import src.analysis.adapters.graph.workflow as workflow_module

    monkeypatch.setattr(workflow_module, "document_ingestion_node", passthrough_document_ingestion)
    monkeypatch.setattr(workflow_module, "pii_anonymizer_node", passthrough_pii)
    monkeypatch.setattr(workflow_module, "save_to_db_node", no_save)

    app = compile_workflow(checkpointer=None, persist_diagram=False)
    result = await app.ainvoke(
        {
            **_base_state(),
            "doc_type": "contract",
            "retry_count": 0,
            "critique_notes": "",
            "human_approval_required": False,
        }
    )

    assert result["project_id"] == "project-1"
