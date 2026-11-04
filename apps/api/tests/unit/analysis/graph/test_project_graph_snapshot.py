"""Focused ProjectGraph durability checks using the existing ADR-015 repository port."""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import ErrorRecord, NodeResult, NodeStatus


class MemorySnapshots:
    def __init__(self):
        self.rows = []

    async def latest(self, project_id, tenant_id):
        return self.rows[-1] if self.rows else None

    async def append_snapshot(self, snapshot):
        self.rows.append(snapshot)
        return snapshot


def state():
    return {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "trigger_event_id": None,
        "previous_snapshot_id": None,
        "changed_artifact_ids": [],
        "artifacts": [DocumentArtifact(document_id=str(uuid4()), doc_type="contract")],
        "coherence_result": ProjectCoherenceResult(
            overall_score=None,
            signal_count=0,
            finding_count=0,
            artifact_count=1,
            llm_on=True,
            score_reason="unassessed",
            insufficient_data_reasons=["BUDGET", "TIME"],
        ),
        "health_result": {"composite_score": None, "status": "unassessed"},
        "node_results": [],
    }


@pytest.mark.asyncio
async def test_real_projectgraph_snapshot_persists_honest_null_and_reuses_result():
    from src.analysis.adapters.graph.project_graph import write_snapshot
    from src.temporal.domain.project_snapshot import SnapshotTrigger

    repo = MemorySnapshots()
    current = {**state(), "snapshot_repository": repo}
    first = await write_snapshot(current)
    again = await write_snapshot(current)

    assert first["node_results"][0].status is NodeStatus.OK
    assert again["node_results"][0].status is NodeStatus.OK
    assert first["snapshot_id"] == again["snapshot_id"]
    assert len(repo.rows) == 1
    snapshot = repo.rows[0]
    assert snapshot.trigger is SnapshotTrigger.GRAPH_COMPLETED
    assert snapshot.coherence_subscore is None
    assert snapshot.health_vector["composite_score"] is None
    assert snapshot.counts["artifact_count"] == 1
    assert snapshot.tenant_id == current["tenant_id"]


@pytest.mark.asyncio
async def test_material_failure_never_acknowledges_trusted_projection(monkeypatch):
    from src.core.tasks import project_graph_tasks

    class ArtifactRepo:
        acknowledged = False

        async def list_trusted_for_project(self, **_kwargs):
            return [DocumentArtifact(document_id=str(uuid4()), doc_type="contract")]

        async def mark_loaded_projected(self, **_kwargs):
            self.acknowledged = True
            return 1

    class BadGraph:
        async def ainvoke(self, state):
            return {
                **state,
                "node_results": [
                    NodeResult(
                        node="cross_doc_coherence",
                        status=NodeStatus.FAILED,
                        error=ErrorRecord(
                            node="cross_doc_coherence",
                            error_type="RuntimeError",
                            message="provider unavailable",
                        ),
                    )
                ],
            }

    repo = ArtifactRepo()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: BadGraph())
    with pytest.raises(RuntimeError, match="material execution incomplete"):
        await project_graph_tasks.run_project_graph_once(
            project_id=uuid4(), tenant_id=uuid4(), artifact_repository=repo,
        )
    assert repo.acknowledged is False


@pytest.mark.asyncio
async def test_missing_snapshot_does_not_acknowledge_project(monkeypatch):
    from src.core.tasks import project_graph_tasks

    class ArtifactRepo:
        acknowledged = False

        async def list_trusted_for_project(self, **_kwargs):
            return [DocumentArtifact(document_id=str(uuid4()), doc_type="contract")]

        async def mark_loaded_projected(self, **_kwargs):
            self.acknowledged = True
            return 1

    class NoSnapshotGraph:
        async def ainvoke(self, state):
            return {**state, "node_results": []}

    repo = ArtifactRepo()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: NoSnapshotGraph())
    with pytest.raises(RuntimeError, match="snapshot missing"):
        await project_graph_tasks.run_project_graph_once(
            project_id=uuid4(),
            tenant_id=uuid4(),
            artifact_repository=repo,
            snapshot_repository=MemorySnapshots(),
        )
    assert repo.acknowledged is False
