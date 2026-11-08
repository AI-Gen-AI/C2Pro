"""G3: raw Coherence evidence -> Alert reconciliation -> review surface.

TS-UT-ADR017-PG-ALERTS-001
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.project_graph_state import CoherenceAlertEvidence
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeResult, NodeStatus
from src.coherence.models import Alert, EnrichedCoherenceResult, Evidence


def _raw_alert() -> Alert:
    evidence = Evidence.model_construct(source_clause_id=str(uuid4()), claim="c", quote="q")
    return Alert.model_construct(
        rule_id="R-1", severity="high", category="general", message="m", evidence=evidence
    )


def _artifact() -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(uuid4()), document_revision_id=str(uuid4()), doc_type="contract"
    )


class _Runner:
    def __init__(self, outcome: dict[str, object] | None = None, error: Exception | None = None):
        self.calls: list[dict[str, object]] = []
        self.outcome = outcome or {"review_alert_ids": []}
        self.error = error

    async def correlate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.outcome


@pytest.mark.asyncio
async def test_cross_doc_coherence_preserves_raw_alerts_and_summary(monkeypatch) -> None:
    from src.analysis.adapters.graph import project_graph

    raw = _raw_alert()

    async def _engine(_clauses, _project_id, *, config, seed_signals, seed_coverage):  # noqa: ARG001
        return EnrichedCoherenceResult(overall_score=70.0, alerts=[raw])

    async def _llm_off(_tenant_id):
        return False

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", _engine)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _llm_off)
    artifact = _artifact()

    result = await project_graph.cross_doc_coherence(
        {"project_id": uuid4(), "tenant_id": uuid4(), "artifacts": [artifact]}
    )

    evidence = result["coherence_alert_evidence"]
    assert evidence.alerts == (raw,)
    assert evidence.alerts[0] is raw
    assert evidence.source_clauses == ()
    assert evidence.artifact_revision_ids == (artifact.document_revision_id,)
    assert result["coherence_result"].overall_score == 70.0
    assert "coherence_score_version" not in result  # snapshot semantics unchanged


@pytest.mark.asyncio
async def test_cross_doc_coherence_without_artifacts_has_no_evidence() -> None:
    from src.analysis.adapters.graph.project_graph import cross_doc_coherence

    result = await cross_doc_coherence(
        {"project_id": uuid4(), "tenant_id": uuid4(), "artifacts": []}
    )
    assert result["coherence_alert_evidence"] is None


@pytest.mark.asyncio
async def test_alert_correlation_passes_raw_alerts_not_summary() -> None:
    from src.analysis.adapters.graph.project_graph import alert_correlation

    raw = _raw_alert()
    clause = object()
    runner = _Runner({"review_alert_ids": ["a"]})
    project_id, tenant_id = uuid4(), uuid4()
    summary = SimpleNamespace(marker="summary")

    result = await alert_correlation(
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "coherence_result": summary,
            "coherence_alert_evidence": CoherenceAlertEvidence(
                alerts=(raw,), source_clauses=(clause,), score_version=None,
                artifact_revision_ids=(),
            ),
            "alert_correlation_runner": runner,
        }
    )

    call = runner.calls[0]
    assert call["evaluation_alerts"] == (raw,)
    assert call["source_clauses"] == (clause,)
    assert call["project_id"] == project_id and call["tenant_id"] == tenant_id
    assert result["node_results"][0].status is NodeStatus.OK


@pytest.mark.asyncio
async def test_alert_correlation_skips_without_raw_evidence_never_reconstructs() -> None:
    from src.analysis.adapters.graph.project_graph import alert_correlation

    runner = _Runner()
    result = await alert_correlation(
        {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "coherence_result": {"overall_score": 50.0},
            "coherence_alert_evidence": None,
            "alert_correlation_runner": runner,
        }
    )
    node = result["node_results"][0]
    assert node.status is NodeStatus.SKIPPED
    assert runner.calls == []


@pytest.mark.asyncio
async def test_alert_correlation_runner_failure_is_failed_not_ok() -> None:
    from src.analysis.adapters.graph.project_graph import alert_correlation

    result = await alert_correlation(
        {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "coherence_alert_evidence": CoherenceAlertEvidence((), (), None, ()),
            "alert_correlation_runner": _Runner(error=RuntimeError("db down")),
        }
    )
    node = result["node_results"][0]
    assert node.status is NodeStatus.FAILED
    assert node.error.message == "db down"


def _correlation_state(status: NodeStatus, data: object = None) -> dict[str, object]:
    return {"node_results": [NodeResult(node="alert_correlation", status=status, data=data)]}


def test_hitl_routing_exposes_review_alerts_without_approving() -> None:
    from src.analysis.adapters.graph.project_graph import hitl_routing

    node = hitl_routing(
        _correlation_state(NodeStatus.OK, {"review_alert_ids": ["a1", "a2"]})
    )["node_results"][0]
    assert node.status is NodeStatus.OK
    assert node.data["review_surface"] == "alerts"
    assert node.data["review_alert_ids"] == ["a1", "a2"]
    assert node.data["requires_human_review_count"] == 2
    assert node.data["auto_approved"] is False


@pytest.mark.parametrize(
    "state",
    [
        {"node_results": []},
        _correlation_state(NodeStatus.SKIPPED),
        _correlation_state(NodeStatus.OK, {"no_review_key": 1}),
    ],
)
def test_hitl_routing_fails_closed_without_reconciliation(state) -> None:
    from src.analysis.adapters.graph.project_graph import hitl_routing

    node = hitl_routing(state)["node_results"][0]
    assert node.status is NodeStatus.SKIPPED
    assert "not evaluated" in node.degradation_reason


class _FakeRecord(SimpleNamespace):
    pass


def _patch_mirror(monkeypatch, records, calls):
    from src.coherence import router

    async def _mirror(**kwargs):
        calls.append(kwargs)
        return router._CoherenceAlertReconciliation(
            finding_keys_by_alert_index=tuple(records),
            records_by_finding_key=records,
        )

    monkeypatch.setattr(router, "_mirror_coherence_alerts_to_alerts_table", _mirror)


@pytest.mark.asyncio
async def test_adapter_uses_same_session_without_auto_resolve(monkeypatch) -> None:
    from src.analysis.adapters.persistence.coherence_alert_correlation import (
        SqlAlchemyCoherenceAlertCorrelationRunner,
    )

    project_id, tenant_id = uuid4(), uuid4()
    review_id, other_id = uuid4(), uuid4()
    records = {
        "k1": _FakeRecord(id=review_id, alert_metadata={"requires_human_review": True}),
        "k2": _FakeRecord(id=other_id, alert_metadata={"requires_human_review": False}),
    }
    calls: list[dict[str, object]] = []
    _patch_mirror(monkeypatch, records, calls)
    session = object()
    raw = [_raw_alert(), _raw_alert()]

    outcome = await SqlAlchemyCoherenceAlertCorrelationRunner(
        session, project_id=project_id, tenant_id=tenant_id
    ).correlate(
        project_id=project_id,
        tenant_id=tenant_id,
        coherence_result=None,
        evaluation_alerts=raw,
        source_clauses=(),
    )

    call = calls[0]
    assert call["db"] is session
    assert call["alerts"] is raw
    assert call["auto_resolve"] is False
    assert call["evaluation_complete"] is False
    assert outcome["review_alert_ids"] == [str(review_id)]
    assert outcome["requires_human_review_count"] == 1
    assert outcome["alerts_submitted"] == 2


@pytest.mark.asyncio
async def test_adapter_rejects_other_tenant_or_project(monkeypatch) -> None:
    from src.analysis.adapters.persistence.coherence_alert_correlation import (
        SqlAlchemyCoherenceAlertCorrelationRunner,
    )

    calls: list[dict[str, object]] = []
    _patch_mirror(monkeypatch, {}, calls)
    project_id, tenant_id = uuid4(), uuid4()
    runner = SqlAlchemyCoherenceAlertCorrelationRunner(
        object(), project_id=project_id, tenant_id=tenant_id
    )
    for bad in ({"tenant_id": uuid4()}, {"project_id": uuid4()}):
        kwargs = {"project_id": project_id, "tenant_id": tenant_id, **bad}
        with pytest.raises(ValueError, match="SCOPE_MISMATCH"):
            await runner.correlate(
                coherence_result=None, evaluation_alerts=[_raw_alert()], source_clauses=(), **kwargs
            )
    assert calls == []


@pytest.mark.asyncio
async def test_adapter_idempotent_resubmission_and_no_alerts_skip_writer(monkeypatch) -> None:
    from src.analysis.adapters.persistence.coherence_alert_correlation import (
        SqlAlchemyCoherenceAlertCorrelationRunner,
    )

    calls: list[dict[str, object]] = []
    rid = uuid4()
    _patch_mirror(
        monkeypatch, {"k": _FakeRecord(id=rid, alert_metadata={"requires_human_review": True})}, calls
    )
    project_id, tenant_id = uuid4(), uuid4()
    runner = SqlAlchemyCoherenceAlertCorrelationRunner(
        object(), project_id=project_id, tenant_id=tenant_id
    )
    args = {
        "project_id": project_id, "tenant_id": tenant_id, "coherence_result": None,
        "source_clauses": (),
    }
    first = await runner.correlate(evaluation_alerts=[_raw_alert()], **args)
    second = await runner.correlate(evaluation_alerts=[_raw_alert()], **args)
    empty = await runner.correlate(evaluation_alerts=[], **args)

    assert first == second  # same durable record set; the mirror owns dedup by fingerprint
    assert empty["alerts_submitted"] == 0 and len(calls) == 2


@pytest.mark.asyncio
async def test_alert_node_without_provider_skips_even_with_raw_evidence() -> None:
    from src.analysis.adapters.graph.project_graph import alert_correlation

    result = await alert_correlation(
        {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "coherence_alert_evidence": CoherenceAlertEvidence((_raw_alert(),), (), None, ()),
        }
    )
    node = result["node_results"][0]
    assert node.status is NodeStatus.SKIPPED
    assert node.degradation_reason == "alert correlation integration unavailable"


@pytest.mark.asyncio
async def test_run_project_graph_async_wires_same_session_runner(monkeypatch) -> None:
    from contextlib import asynccontextmanager

    from src.analysis.adapters.persistence.coherence_alert_correlation import (
        SqlAlchemyCoherenceAlertCorrelationRunner,
    )
    from src.core.tasks import project_graph_tasks

    class _Session:
        async def execute(self, *_a, **_k):
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

    class _Governance:
        requeue_countdown_seconds = 1

        async def acquire_tenant_slot(self, _t):
            return True

        async def release_tenant_slot(self, _t):
            return None

        async def clear_project_pending(self, _p):
            return None

    session = _Session()
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def _raw_session():
        yield session

    async def _noop(*_a, **_k):
        return []

    async def _once(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "structured_source_comparison": None}

    monkeypatch.setattr(project_graph_tasks, "init_db", lambda: None)
    monkeypatch.setattr(project_graph_tasks, "get_raw_session", _raw_session)
    monkeypatch.setattr(project_graph_tasks, "run_project_graph_once", _once)
    monkeypatch.setattr(project_graph_tasks, "persist_provisional_source_discrepancies", _noop)
    monkeypatch.setattr(
        "src.documents.application.structured_source_units.load_canonical_source_units", _noop
    )
    monkeypatch.setattr(
        "src.analysis.adapters.graph.source_clause_evidence.load_revision_bound_source_quotes",
        _noop,
    )
    project_id, tenant_id = uuid4(), uuid4()

    await project_graph_tasks._run_project_graph_async(
        project_id=project_id, tenant_id=tenant_id, governance=_Governance()
    )

    runner = captured["alert_correlation_runner"]
    assert isinstance(runner, SqlAlchemyCoherenceAlertCorrelationRunner)
    assert runner._session is session
    assert (runner._project_id, runner._tenant_id) == (project_id, tenant_id)
