"""Cross-document coherence ProjectGraph tests (ADR-017 / TASK-V3-017-04).

TS-UT-ADR017-XDOC-001
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.analysis.domain.contracts import (
    CoherenceFinding,
    DocumentArtifact,
    RiskItem,
    Severity,
)
from src.analysis.domain.node_result import NodeStatus
from src.coherence.models import (
    CategoryBreakdown,
    EnrichedCoherenceResult,
    SeverityCount,
)


def _artifact(
    document_id: str,
    *,
    doc_type: str,
    risk_category: str,
) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=document_id,
        document_revision_id=str(uuid4()),
        doc_type=doc_type,
        document_category=risk_category,
        extracted_risks=[
            RiskItem(
                title=f"{risk_category} risk",
                description="risk description",
                category=risk_category,
                impact=Severity.HIGH,
                confidence=0.8,
                source="source text",
            )
        ],
        coherence_findings=[
            CoherenceFinding(
                category=risk_category,
                message=f"{risk_category} finding",
                rule_id=f"FIND-{risk_category}",
                severity=Severity.MEDIUM,
                score=60,
                confidence=0.75,
                evidence_ref="artifact",
            )
        ],
    )


def _state(*, artifacts: list[DocumentArtifact]) -> dict[str, object]:
    return {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "trigger_event_id": None,
        "previous_snapshot_id": None,
        "changed_artifact_ids": [],
        "artifacts": artifacts,
        "coherence_result": None,
        "impact_result": None,
        "health_result": None,
        "snapshot_id": None,
        "node_results": [],
    }


def _engine_result() -> EnrichedCoherenceResult:
    return EnrichedCoherenceResult(
        overall_score=82.5,
        category_breakdown=[
            CategoryBreakdown(
                category="legal",
                score=80,
                alert_count=1,
                severity_breakdown=SeverityCount(medium=1),
                impact_percentage=20,
                state="assessed_findings",
            )
        ],
        calculated_at=datetime.now(UTC),
        score_reason=None,
        score_missing_dimensions=["TIME"],
    )


def _disable_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
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
        lambda: {"parent": None, "project_name": None, "enabled": False, "metadata": {}, "tags": []},
    )
    monkeypatch.setattr(langsmith_utils, "tracing_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "_tracing_v2_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "tracing_v2_enabled", _disabled_tracing_v2)
    monkeypatch.setattr(
        "langchain_core.callbacks.manager._get_tracer_project",
        lambda *_args, **_kwargs: "default",
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_core.tracers.context._get_tracer_project",
        lambda *_args, **_kwargs: "default",
        raising=False,
    )


@pytest.mark.asyncio
async def test_cross_doc_coherence_aggregates_signals_and_returns_typed_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph import project_graph
    from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult

    captured: dict[str, object] = {}

    async def _fake_evaluate(clauses, project_id, *, config, seed_signals, seed_coverage):
        captured["clauses"] = clauses
        captured["project_id"] = project_id
        captured["config"] = config
        captured["seed_signals"] = seed_signals
        captured["seed_coverage"] = seed_coverage
        return _engine_result()

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", _fake_evaluate)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _enabled)

    result = await project_graph.cross_doc_coherence(
        _state(
            artifacts=[
                _artifact("contract-doc", doc_type="contract", risk_category="LEGAL"),
                _artifact("schedule-doc", doc_type="schedule", risk_category="SCHEDULE"),
            ]
        )
    )

    summary = result["coherence_result"]
    assert isinstance(summary, ProjectCoherenceResult)
    assert summary.overall_score == 82.5
    assert summary.artifact_count == 2
    assert summary.llm_on is True
    assert summary.signal_count >= 4
    assert summary.finding_count == 2
    assert summary.insufficient_data_reasons == ["TIME"]
    assert result["node_results"][0].status is NodeStatus.OK

    signals = captured["seed_signals"]
    assert {signal.raw_data["artifact_id"] for signal in signals} == {
        "contract-doc",
        "schedule-doc",
    }
    assert captured["seed_coverage"]["LEGAL"] is True
    assert captured["seed_coverage"]["TIME"] is True
    assert captured["clauses"] == []


@pytest.mark.asyncio
async def test_cross_doc_coherence_llm_gate_sets_low_budget_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph import project_graph

    configs: list[object] = []

    async def _fake_evaluate(_clauses, _project_id, *, config, seed_signals, seed_coverage):
        configs.append(config)
        return _engine_result()

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", _fake_evaluate)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _disabled)
    await project_graph.cross_doc_coherence(
        _state(artifacts=[_artifact("contract-doc", doc_type="contract", risk_category="LEGAL")])
    )

    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _enabled)
    await project_graph.cross_doc_coherence(
        _state(artifacts=[_artifact("budget-doc", doc_type="budget", risk_category="BUDGET")])
    )

    assert configs[0].low_budget_mode is True
    assert configs[1].low_budget_mode is False


@pytest.mark.asyncio
async def test_cross_doc_coherence_honest_null_on_empty_or_engine_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph import project_graph

    empty = await project_graph.cross_doc_coherence(_state(artifacts=[]))
    assert empty["coherence_result"] is None
    assert empty["node_results"][0].status is NodeStatus.SKIPPED

    async def _explode(*_args, **_kwargs):
        raise RuntimeError("engine unavailable")

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", _explode)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _enabled)

    degraded = await project_graph.cross_doc_coherence(
        _state(artifacts=[_artifact("contract-doc", doc_type="contract", risk_category="LEGAL")])
    )

    assert degraded["coherence_result"] is None
    assert degraded["node_results"][0].status is NodeStatus.DEGRADED
    assert "engine unavailable" in (degraded["node_results"][0].degradation_reason or "")


def test_project_coherence_result_is_frozen_and_drift_locked() -> None:
    from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult

    result = ProjectCoherenceResult(
        overall_score=None,
        category_scores={},
        signal_count=0,
        finding_count=0,
        artifact_count=0,
        llm_on=False,
        insufficient_data_reasons=["missing"],
    )

    with pytest.raises(ValidationError):
        ProjectCoherenceResult.model_validate(
            {
                "overall_score": None,
                "category_scores": {},
                "signal_count": 0,
                "finding_count": 0,
                "artifact_count": 0,
                "llm_on": False,
                "insufficient_data_reasons": [],
                "extra": "drift",
            }
        )
    with pytest.raises(ValidationError):
        result.artifact_count = 1


@pytest.mark.asyncio
async def test_run_project_graph_once_populates_cross_doc_coherence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph import project_graph
    from src.core.tasks.project_graph_tasks import run_project_graph_once

    class Repo:
        async def list_active_for_project(self, *, project_id, tenant_id):
            return [
                _artifact("contract-doc", doc_type="contract", risk_category="LEGAL"),
                _artifact("budget-doc", doc_type="budget", risk_category="BUDGET"),
            ]

    async def _fake_evaluate(_clauses, _project_id, *, config, seed_signals, seed_coverage):
        return _engine_result()

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", _fake_evaluate)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _enabled)
    _disable_tracing(monkeypatch)

    result = await run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=Repo(),
    )

    assert result["status"] == "ok"
    assert result["artifact_count"] == 2
    assert result["coherence_result"]["artifact_count"] == 2
    by_node = {node_result.node: node_result for node_result in result["node_results"]}
    assert by_node["cross_doc_coherence"].status is NodeStatus.OK


def test_cross_doc_coherence_does_not_call_raw_llm_or_bypass_anonymization() -> None:
    import inspect

    from src.analysis.adapters.graph import project_graph

    source = inspect.getsource(project_graph.cross_doc_coherence)
    assert "generate_structured" not in source
    assert "anthropic" not in source.lower()
    assert "bypass_anonymization" not in source


async def _enabled(_tenant_id) -> bool:
    return True


async def _disabled(_tenant_id) -> bool:
    return False
