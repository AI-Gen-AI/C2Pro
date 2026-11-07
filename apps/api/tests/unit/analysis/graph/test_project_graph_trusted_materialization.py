"""P1 trusted ProjectGraph persistence and integration seams."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.analysis.adapters.persistence.trusted_artifact_graph_materializer import (
    KnowledgeGraphMaterialization,
)
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeResult, NodeStatus


class _Artifacts:
    def __init__(self, artifacts: list[DocumentArtifact]) -> None:
        self.artifacts = artifacts
        self.acknowledged = False

    async def list_trusted_for_project(self, **_kwargs):
        return self.artifacts

    async def mark_loaded_projected(self, **_kwargs):
        self.acknowledged = True
        return len(self.artifacts)


class _Graph:
    def __init__(self) -> None:
        self.state = None

    async def ainvoke(self, state):
        self.state = state
        return {
            **state,
            "snapshot_id": uuid4(),
            "node_results": [NodeResult(node="cross_doc_coherence", status=NodeStatus.OK)],
        }


class _Materializer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def materialize_trusted_artifacts(self, **kwargs):
        self.calls.append(kwargs)
        return KnowledgeGraphMaterialization(node_count=2, edge_count=1)


class _ScalarResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _MaterializerSession:
    def __init__(self, project_id) -> None:
        self.project_id = project_id
        self.statements = []
        self.node_ids = [uuid4(), uuid4()]

    async def execute(self, statement):
        self.statements.append(statement)
        table = getattr(statement, "table", None)
        if table is None:  # tenant-scoped ProjectORM authorization select
            return _ScalarResult(self.project_id)
        if table.name == "knowledge_graph_nodes":
            return _ScalarResult(self.node_ids.pop(0))
        return _ScalarResult(None)


@pytest.mark.asyncio
async def test_completed_trusted_graph_materializes_before_projection_ack(monkeypatch):
    from src.core.tasks import project_graph_tasks

    artifact = DocumentArtifact(
        document_id=str(uuid4()),
        document_revision_id=str(uuid4()),
        doc_type="contract",
    )
    repository = _Artifacts([artifact])
    materializer = _Materializer()
    graph = _Graph()
    runner = object()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: graph)

    result = await project_graph_tasks.run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=repository,
        snapshot_repository=object(),
        knowledge_graph_materializer=materializer,
        alert_correlation_runner=runner,
    )

    assert repository.acknowledged is True
    assert materializer.calls[0]["artifacts"] == [artifact]
    assert result["knowledge_graph_materialization"] == {"node_count": 2, "edge_count": 1}
    assert graph.state["alert_correlation_runner"] is runner


@pytest.mark.asyncio
async def test_canonical_materializer_writes_only_trusted_identity_and_edge() -> None:
    from src.analysis.adapters.persistence.trusted_artifact_graph_materializer import (
        SqlAlchemyTrustedArtifactGraphMaterializer,
    )

    project_id = uuid4()
    document_id = uuid4()
    session = _MaterializerSession(project_id)
    result = await SqlAlchemyTrustedArtifactGraphMaterializer(session).materialize_trusted_artifacts(
        project_id=project_id,
        tenant_id=uuid4(),
        artifacts=[
            DocumentArtifact(
                document_id=str(document_id),
                document_revision_id=str(uuid4()),
                doc_type="specification",
            )
        ],
    )

    assert result == KnowledgeGraphMaterialization(node_count=2, edge_count=1)
    node_statements = [
        statement for statement in session.statements
        if getattr(statement, "table", None) is not None
        and statement.table.name == "knowledge_graph_nodes"
    ]
    edge_statement = next(
        statement for statement in session.statements
        if getattr(statement, "table", None) is not None
        and statement.table.name == "knowledge_graph_edges"
    )
    document_params = node_statements[1].compile().params
    edge_params = edge_statement.compile().params
    assert document_params["entity_type"] == "TRUSTED_DOCUMENT"
    assert document_params["entity_id"] == document_id
    assert document_params["properties"]["trust_state"] == "trusted"
    assert document_params["properties"]["evidence_state"] == "trusted_artifact_identity_only"
    assert edge_params["relationship_type"] == "HAS_TRUSTED_DOCUMENT_ARTIFACT"
    assert edge_params["properties"]["trust_state"] == "trusted"


@pytest.mark.asyncio
async def test_graph_materialization_failure_keeps_trusted_projection_pending(monkeypatch):
    from src.core.tasks import project_graph_tasks

    class FailingMaterializer:
        async def materialize_trusted_artifacts(self, **_kwargs):
            raise RuntimeError("canonical KG unavailable")

    repository = _Artifacts([DocumentArtifact(document_id=str(uuid4()), doc_type="contract")])
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: _Graph())

    with pytest.raises(RuntimeError, match="canonical KG unavailable"):
        await project_graph_tasks.run_project_graph_once(
            project_id=uuid4(),
            tenant_id=uuid4(),
            artifact_repository=repository,
            snapshot_repository=object(),
            knowledge_graph_materializer=FailingMaterializer(),
        )
    assert repository.acknowledged is False


@pytest.mark.asyncio
async def test_graph_snapshot_reuses_honest_null_coherence() -> None:
    from src.analysis.adapters.graph.project_graph import write_snapshot
    from src.temporal.domain.project_snapshot import SnapshotTrigger

    class Snapshots:
        def __init__(self) -> None:
            self.rows = []

        async def latest(self, *_args):
            return self.rows[-1] if self.rows else None

        async def append_snapshot(self, value):
            self.rows.append(value)
            return value

    snapshots = Snapshots()
    state = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "trigger_event_id": None,
        "artifacts": [DocumentArtifact(document_id=str(uuid4()), doc_type="contract")],
        "coherence_result": ProjectCoherenceResult(
            overall_score=None,
            signal_count=0,
            finding_count=0,
            artifact_count=1,
            llm_on=False,
            insufficient_data_reasons=["BUDGET", "TIME"],
            score_reason="insufficient_trusted_evidence",
        ),
        "health_result": {"composite_score": None, "status": "unassessed"},
        "snapshot_repository": snapshots,
    }

    first = await write_snapshot(state)
    second = await write_snapshot(state)

    assert first["snapshot_id"] == second["snapshot_id"]
    assert len(snapshots.rows) == 1
    assert snapshots.rows[0].trigger is SnapshotTrigger.GRAPH_COMPLETED
    assert snapshots.rows[0].coherence_subscore is None
    assert snapshots.rows[0].counts["score_reason"] == "insufficient_trusted_evidence"


@pytest.mark.asyncio
async def test_alert_correlation_is_explicitly_pending_until_alerts_integration() -> None:
    from src.analysis.adapters.graph.project_graph import alert_correlation

    result = await alert_correlation(
        {"project_id": uuid4(), "tenant_id": uuid4(), "coherence_result": None}
    )

    node = result["node_results"][0]
    assert node.status is NodeStatus.SKIPPED
    assert node.degradation_reason == "alert correlation integration unavailable"
