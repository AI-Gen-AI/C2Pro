"""ProjectGraph trigger tests (ADR-017 / TASK-V3-017-03).

TS-UT-ADR017-TRG-001
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact
from src.core.tenants.types import TenantId


class _FakeGraph:
    async def ainvoke(self, state):
        return {**state, "ran": True}


class _FakeRepo:
    def __init__(self, artifacts: list[DocumentArtifact]) -> None:
        self.artifacts = artifacts

    async def list_trusted_for_project(self, *, project_id, tenant_id):
        return self.artifacts


def _artifact() -> DocumentArtifact:
    return DocumentArtifact(document_id=str(uuid4()), doc_type="contract")


@pytest.mark.asyncio
async def test_enqueue_project_graph_flag_off_suppresses_delay(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    async def _disabled(_tenant_id):
        return False

    calls: list[dict[str, str | None]] = []
    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", _disabled)
    monkeypatch.setattr(
        project_graph_tasks.run_project_graph, "delay", lambda **kwargs: calls.append(kwargs)
    )

    result = await project_graph_tasks.enqueue_project_graph(
        project_id=uuid4(),
        tenant_id=uuid4(),
    )

    assert result is None
    assert calls == []


@pytest.mark.asyncio
async def test_enqueue_project_graph_flag_on_calls_delay(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    async def _enabled(_tenant_id):
        return True

    calls: list[dict[str, str | None]] = []
    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", _enabled)
    monkeypatch.setattr(
        project_graph_tasks.run_project_graph, "delay", lambda **kwargs: calls.append(kwargs)
    )

    project_id = uuid4()
    tenant_id = uuid4()
    result = await project_graph_tasks.enqueue_project_graph(
        project_id=project_id,
        tenant_id=tenant_id,
    )

    assert result is None
    assert calls == [
        {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "trigger_event_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_run_project_graph_once_loads_artifacts_and_runs_skeleton(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    artifact = _artifact()
    fake_graph = _FakeGraph()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: fake_graph)

    result = await project_graph_tasks.run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=_FakeRepo([artifact]),
    )

    assert result["status"] == "ok"
    assert result["artifact_count"] == 1


def test_run_project_graph_normalizes_tenant_once_at_task_boundary(monkeypatch) -> None:
    """TS-UT-ADR017-TRG-001: normalize serialized tenant before graph application code."""
    from src.core.tasks import project_graph_tasks

    project_id = uuid4()
    raw_tenant_id = str(uuid4())
    normalized_tenant_id = TenantId(uuid4())
    normalize = Mock(return_value=normalized_tenant_id)
    captured: dict[str, object] = {}

    async def fake_run_project_graph_async(**kwargs):
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(project_graph_tasks, "require_tenant_id", normalize, raising=False)
    monkeypatch.setattr(
        project_graph_tasks,
        "_run_project_graph_async",
        fake_run_project_graph_async,
    )

    result = project_graph_tasks.run_project_graph(
        None,
        project_id=str(project_id),
        tenant_id=raw_tenant_id,
    )

    normalize.assert_called_once_with(raw_tenant_id)
    assert captured["tenant_id"] is normalized_tenant_id
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_tier1_completion_swallow_store_and_enqueue_errors(monkeypatch) -> None:
    from src.analysis.application import document_artifact_completion

    async def _explode(*_args, **_kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(document_artifact_completion, "_persist_artifact", _explode)

    await document_artifact_completion.persist_artifact_and_enqueue_project_graph(
        {
            "project_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "document_id": str(uuid4()),
            "doc_type": "contract",
        }
    )


@pytest.mark.asyncio
async def test_document_artifact_completion_normalizes_tenant_at_state_boundary(
    monkeypatch,
) -> None:
    """TS-UT-ADR017-TRG-001: normalize graph-state tenant before persistence ports."""
    from src.analysis.application import document_artifact_completion

    project_id = uuid4()
    raw_tenant_id = str(uuid4())
    normalized_tenant_id = TenantId(uuid4())
    normalize = Mock(return_value=normalized_tenant_id)
    captured: dict[str, object] = {}

    class FakeSession:
        async def execute(self, _statement):
            return None

        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

    class FakeRepository:
        def __init__(self, _session) -> None:
            pass

        async def save(self, _artifact, **kwargs):
            captured.update(kwargs)

    @asynccontextmanager
    async def fake_raw_session():
        yield FakeSession()

    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        document_artifact_completion,
        "require_tenant_id",
        normalize,
        raising=False,
    )
    monkeypatch.setattr(document_artifact_completion, "init_db", no_op)
    monkeypatch.setattr(document_artifact_completion, "get_raw_session", fake_raw_session)
    monkeypatch.setattr(
        document_artifact_completion,
        "SqlAlchemyDocumentArtifactRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        document_artifact_completion,
        "build_document_artifact",
        lambda _state: SimpleNamespace(),
    )
    monkeypatch.setattr(document_artifact_completion, "enqueue_project_graph", no_op)

    await document_artifact_completion._persist_artifact(
        {
            "project_id": str(project_id),
            "tenant_id": raw_tenant_id,
        }
    )

    normalize.assert_called_once_with(raw_tenant_id)
    assert captured["tenant_id"] is normalized_tenant_id


@pytest.mark.asyncio
async def test_hitl_candidate_persists_without_canonical_project_graph_enqueue(
    monkeypatch,
) -> None:
    """#714: PROPOSED output may persist, but cannot become canonical."""
    from src.analysis.application import document_artifact_completion

    persisted: list[dict[str, object]] = []
    enqueued: list[tuple[object, object]] = []

    class FakeSession:
        async def execute(self, _statement):
            return None

        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

    class FakeRepository:
        def __init__(self, _session) -> None:
            pass

        async def save(self, artifact, **kwargs):
            persisted.append({"artifact": artifact, **kwargs})
            return artifact

    @asynccontextmanager
    async def fake_raw_session():
        yield FakeSession()

    async def no_op(*_args, **_kwargs):
        return None

    async def capture_enqueue(*, project_id, tenant_id, **_kwargs):
        enqueued.append((project_id, tenant_id))

    monkeypatch.setattr(document_artifact_completion, "init_db", no_op)
    monkeypatch.setattr(document_artifact_completion, "get_raw_session", fake_raw_session)
    monkeypatch.setattr(
        document_artifact_completion,
        "SqlAlchemyDocumentArtifactRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        document_artifact_completion,
        "build_document_artifact",
        lambda _state: SimpleNamespace(),
    )
    monkeypatch.setattr(
        document_artifact_completion,
        "enqueue_project_graph",
        capture_enqueue,
    )

    await document_artifact_completion._persist_artifact(
        {
            "project_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "document_id": str(uuid4()),
            "human_approval_required": True,
        }
    )

    assert len(persisted) == 1
    assert enqueued == []


@pytest.mark.asyncio
async def test_non_hitl_artifact_still_enqueues_canonical_project_graph_once(
    monkeypatch,
) -> None:
    """#714: trusted/non-gated completion preserves the existing Tier-2 path."""
    from src.analysis.application import document_artifact_completion

    enqueued: list[tuple[object, object]] = []

    class FakeSession:
        async def execute(self, _statement):
            return None

        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

    class FakeRepository:
        def __init__(self, _session) -> None:
            pass

        async def save(self, artifact, **_kwargs):
            return artifact

    @asynccontextmanager
    async def fake_raw_session():
        yield FakeSession()

    async def no_op(*_args, **_kwargs):
        return None

    async def capture_enqueue(*, project_id, tenant_id, **_kwargs):
        enqueued.append((project_id, tenant_id))

    monkeypatch.setattr(document_artifact_completion, "init_db", no_op)
    monkeypatch.setattr(document_artifact_completion, "get_raw_session", fake_raw_session)
    monkeypatch.setattr(
        document_artifact_completion,
        "SqlAlchemyDocumentArtifactRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        document_artifact_completion,
        "build_document_artifact",
        lambda _state: SimpleNamespace(),
    )
    monkeypatch.setattr(
        document_artifact_completion,
        "enqueue_project_graph",
        capture_enqueue,
    )

    project_id = uuid4()
    tenant_id = uuid4()
    await document_artifact_completion._persist_artifact(
        {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "document_id": str(uuid4()),
            "human_approval_required": False,
        }
    )

    assert enqueued == [(project_id, tenant_id)]


@pytest.mark.asyncio
async def test_project_graph_loads_trusted_artifacts_not_merely_active_candidates(
    monkeypatch,
) -> None:
    """#714: a newer PROPOSED candidate must not displace canonical TRUSTED."""
    from src.core.tasks import project_graph_tasks

    trusted = _artifact()
    proposed = _artifact()

    class TrustAwareRepo:
        def __init__(self) -> None:
            self.trusted_calls = 0
            self.active_calls = 0

        async def list_trusted_for_project(self, *, project_id, tenant_id):
            self.trusted_calls += 1
            return [trusted]

        async def list_active_for_project(self, *, project_id, tenant_id):
            self.active_calls += 1
            return [proposed]

    repo = TrustAwareRepo()
    fake_graph = _FakeGraph()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: fake_graph)

    result = await project_graph_tasks.run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=repo,
    )

    assert result["artifact_count"] == 1
    assert repo.trusted_calls == 1
    assert repo.active_calls == 0


def test_structured_xlsx_revisions_are_distinct_source_only_observations():
    """Canonical source refs must not be counted as trusted analysis artifacts."""
    from src.core.tasks.project_graph_tasks import summarize_canonical_source_revisions

    doc_budget, doc_schedule = uuid4(), uuid4()
    rev_budget, rev_schedule = uuid4(), uuid4()
    budget = {
        "family": "budget",
        "document_id": doc_budget,
        "revision_id": rev_budget,
        "blob_hash": "a" * 64,
    }
    schedule = {
        "family": "schedule",
        "document_id": doc_schedule,
        "revision_id": rev_schedule,
        "blob_hash": "b" * 64,
    }
    refs = summarize_canonical_source_revisions(
        [
            budget,
            budget,
            schedule,
            {**budget, "revision_id": None},  # unbound is not usable evidence
        ]
    )
    assert len(refs) == 2
    assert {ref["family"]: ref["observed_rows"] for ref in refs} == {
        "budget": 2,
        "schedule": 1,
    }
    assert all(ref["role"] == "source_observation_only_not_approved_baseline" for ref in refs)
    assert all(ref["revision_id"] and ref["blob_sha256"] for ref in refs)


@pytest.mark.asyncio
async def test_project_graph_observes_xlsx_revisions_without_promoting_them(monkeypatch):
    from src.analysis.adapters.graph.project_graph import align_entities, load_current_artifacts
    from src.core.tasks import project_graph_tasks

    trusted_contract = _artifact()
    refs = [
        {
            "family": "budget",
            "document_id": str(uuid4()),
            "revision_id": str(uuid4()),
            "blob_sha256": "a" * 64,
            "observed_rows": 3,
            "role": "source_observation_only_not_approved_baseline",
        },
        {
            "family": "schedule",
            "document_id": str(uuid4()),
            "revision_id": str(uuid4()),
            "blob_sha256": "b" * 64,
            "observed_rows": 4,
            "role": "source_observation_only_not_approved_baseline",
        },
    ]

    class CaptureGraph:
        async def ainvoke(self, state):
            self.state = state
            return state

    graph = CaptureGraph()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: graph)
    result = await project_graph_tasks.run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=_FakeRepo([trusted_contract]),
        structured_source_refs=refs,
    )
    assert result["artifact_count"] == 1
    assert result["structured_source_revision_count"] == 2
    assert len(graph.state["artifacts"]) == 1
    assert graph.state["structured_source_refs"] == refs
    loaded = load_current_artifacts(graph.state)["node_results"][0].data
    aligned = align_entities(graph.state)["node_results"][0].data
    assert loaded["artifact_count"] == 1
    assert loaded["structured_source_revision_count"] == 2
    assert loaded["structured_source_role"] == "source_evidence_only_not_projected"
    assert set(aligned["structured_source_revision_groups"]) == {"budget", "schedule"}


@pytest.mark.asyncio
async def test_project_graph_consumes_canonical_state_from_exact_trusted_set(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks
    from src.project_state.application.materialize_trusted_state import MaterializationOutcome
    from src.project_state.domain.aggregate import ProjectState

    doc_id, revision, project_id, tenant_id = (uuid4() for _ in range(4))
    trusted = DocumentArtifact(
        document_id=str(doc_id), document_revision_id=str(revision), doc_type="contract"
    )
    state = ProjectState(
        project_id=project_id, tenant_id=tenant_id, document_revision_ids=[revision]
    )
    seen = {}

    class CaptureGraph:
        async def ainvoke(self, graph_input):
            seen.update(graph_input)
            return {**graph_input, "ran": True}

    async def materialize(current):
        assert current == [trusted]
        return MaterializationOutcome("created", 1, 1, 1, 0), state

    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: CaptureGraph())
    result = await project_graph_tasks.run_project_graph_once(
        project_id=project_id,
        tenant_id=tenant_id,
        artifact_repository=_FakeRepo([trusted]),
        canonical_state_materializer=materialize,
    )
    assert result["canonical_state_materialization"] == {
        "status": "created",
        "clause_count": 1,
        "risk_count": 1,
        "trusted_revisions": 1,
        "rejected_unverified_risks": 0,
    }
    assert seen["canonical_project_state"] is state
    assert seen["canonical_materialization_status"] == "created"


@pytest.mark.asyncio
async def test_canonical_materialization_block_is_explicit_not_canonical_score(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks
    from src.project_state.application.materialize_trusted_state import MaterializationOutcome

    source = DocumentArtifact(
        document_id=str(uuid4()), document_revision_id=str(uuid4()), doc_type="contract"
    )
    seen = {}

    class CaptureGraph:
        async def ainvoke(self, graph_input):
            seen.update(graph_input)
            return {**graph_input}

    async def materialize(_current):
        return MaterializationOutcome("source_provenance_unavailable", 0, 0, 1, 1), None

    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: CaptureGraph())
    result = await project_graph_tasks.run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=_FakeRepo([source]),
        canonical_state_materializer=materialize,
    )
    assert result["canonical_state_materialization"]["status"] == "source_provenance_unavailable"
    assert result["status"] == "partial_canonical_state"
    assert result["projected_obligations"] == 0
    assert seen["canonical_materialization_status"] == "source_provenance_unavailable"
    assert "canonical_project_state" not in seen


@pytest.mark.asyncio
async def test_cross_tenant_canonical_materialization_ack_fails_closed(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks
    from src.project_state.application.materialize_trusted_state import MaterializationOutcome
    from src.project_state.domain.aggregate import ProjectState

    project_id, tenant_id, different_tenant, rev = (uuid4(), uuid4(), uuid4(), uuid4())
    source = DocumentArtifact(
        document_id=str(uuid4()), document_revision_id=str(rev), doc_type="contract"
    )

    async def materialize(_current):
        return (
            MaterializationOutcome("created", 1, 1, 1, 0),
            ProjectState(
                project_id=project_id,
                tenant_id=different_tenant,
                document_revision_ids=[rev],
            ),
        )

    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: _FakeGraph())
    with pytest.raises(RuntimeError, match="IDENTITY_MISMATCH"):
        await project_graph_tasks.run_project_graph_once(
            project_id=project_id,
            tenant_id=tenant_id,
            artifact_repository=_FakeRepo([source]),
            canonical_state_materializer=materialize,
        )


@pytest.mark.asyncio
async def test_stale_trusted_revision_cannot_be_acknowledged_as_fresh(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks
    from src.project_state.application.materialize_trusted_state import MaterializationOutcome
    from src.project_state.domain.aggregate import ProjectState

    project_id, tenant_id, rev = uuid4(), uuid4(), uuid4()
    source = DocumentArtifact(
        document_id=str(uuid4()), document_revision_id=str(rev), doc_type="contract"
    )

    async def materialize(_current):
        return (
            MaterializationOutcome("unchanged", 1, 1, 1, 0),
            ProjectState(
                project_id=project_id,
                tenant_id=tenant_id,
                document_revision_ids=[uuid4()],
            ),
        )

    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: _FakeGraph())
    with pytest.raises(RuntimeError, match="REVISION_MISMATCH"):
        await project_graph_tasks.run_project_graph_once(
            project_id=project_id,
            tenant_id=tenant_id,
            artifact_repository=_FakeRepo([source]),
            canonical_state_materializer=materialize,
        )
