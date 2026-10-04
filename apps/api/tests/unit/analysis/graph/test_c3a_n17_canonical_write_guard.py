"""C3a: an untrusted (review-required) run never mutates canonical state at N17.

TS-UT-C3A-N17-GUARD-001. With ``C2PRO_SKIP_HITL`` / ``C2PRO_AI_MOCK`` the graph
routes past N13 and reaches N17 while ``human_approval_required`` is still True
-- the same state for which the #714 completion persists a PROPOSED artifact
(``document_artifact_completion._requires_human_approval``). N17 consumes that
same gate: no analysis row, no risk alerts, no canonical WBS replacement, no
``graph.completed`` snapshot. A genuine approval (N13 sets the flag to False) and
a non-gated run persist exactly as before.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.node_result import NodeStatus

pytestmark = pytest.mark.asyncio

TENANT = "00000000-0000-0000-0000-000000000099"


def _state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "project_id": "00000000-0000-0000-0000-000000000001",
        "document_id": "00000000-0000-0000-0000-000000000002",
        "tenant_id": TENANT,
        "messages": [],
        "node_results": [],
        "extracted_risks": [{"title": "Penalty", "description": "5% per week", "severity": "high"}],
        "extracted_wbs": [{"code": "1", "name": "Works"}],
        "coherence_score": 70,
        "coherence_breakdown": {},
        "human_approval_required": False,
        "analysis_id": None,
    }
    state.update(overrides)
    return state


class _Recorder:
    def __init__(self) -> None:
        self.persisted: list[Any] = []
        self.fenced: list[Any] = []
        self.events: list[dict[str, Any]] = []
        self.sessions = 0


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    from src.analysis.adapters.graph import nodes
    from src.analysis.application import persist_analysis_use_case as persist_module
    from src.analysis.application import persist_resume_analysis as resume_module

    seen = _Recorder()

    class _Session:
        async def __aenter__(self) -> object:
            seen.sessions += 1
            return object()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    class _PersistUseCase:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def execute(self, command: Any) -> Any:
            seen.persisted.append(command)
            return persist_module.PersistAnalysisResult(analysis_id=uuid4())

    async def _fenced(*, state: dict[str, Any], provenance: Any) -> Any:
        seen.fenced.append((state, provenance))

        class _Result:
            analysis_id = uuid4()
            created = True

        return _Result()

    async def _fence(_session: object) -> None:
        return None

    async def _event(**kwargs: Any) -> UUID:
        seen.events.append(kwargs)
        return uuid4()

    monkeypatch.setattr(persist_module, "PersistAnalysisUseCase", _PersistUseCase)
    monkeypatch.setattr(resume_module, "persist_resume_analysis_atomically", _fenced)
    monkeypatch.setattr(nodes, "get_session_with_tenant", lambda _t: _Session(), raising=False)
    monkeypatch.setattr(nodes, "fence_current", _fence, raising=False)
    monkeypatch.setattr(nodes, "record_project_event_and_enqueue_snapshot", _event, raising=False)
    return seen


@pytest.mark.parametrize("flag", [True, None, "yes"])
async def test_review_required_run_writes_no_canonical_state(
    recorder: _Recorder, monkeypatch: pytest.MonkeyPatch, flag: Any
) -> None:
    """(20)(21) skip-HITL: a PROPOSED-bound run cannot replace WBS or create alerts."""
    from src.analysis.adapters.graph import nodes

    monkeypatch.setenv("C2PRO_SKIP_HITL", "1")
    state = _state(human_approval_required=flag)
    if flag is None:
        state.pop("human_approval_required")

    result = await nodes.save_to_db_node(state)  # type: ignore[arg-type]

    assert recorder.persisted == []  # no analysis row, no alerts, no WBS replacement
    assert recorder.events == []  # no graph.completed snapshot
    assert recorder.sessions == 0  # not even a write session is opened
    assert result.get("analysis_id") is None
    node_result = result["node_results"][-1]
    assert node_result.node == "save_to_db"
    assert node_result.status is NodeStatus.SKIPPED
    assert node_result.degradation_reason == "canonical_write_requires_trusted_approval"


async def test_fenced_resume_still_pending_writes_nothing(recorder: _Recorder) -> None:
    """The resume path is guarded by the same gate, not only the legacy path."""
    from src.analysis.adapters.graph import nodes

    state = _state(
        human_approval_required=True,
        resume_provenance={
            "operation_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "owner_token": str(uuid4()),
            "fencing_token": 3,
            "decision_revision": 1,
        },
    )

    result = await nodes.save_to_db_node(state)  # type: ignore[arg-type]

    assert recorder.fenced == [] and recorder.persisted == []
    assert result["node_results"][-1].status is NodeStatus.SKIPPED


async def test_genuine_trusted_path_updates_canonical_state(recorder: _Recorder) -> None:
    """(22) a non-gated or human-approved run (flag explicitly False) persists as before."""
    from src.analysis.adapters.graph import nodes

    result = await nodes.save_to_db_node(_state(human_approval_required=False))  # type: ignore[arg-type]

    [command] = recorder.persisted
    assert command.extracted_risks and command.extracted_wbs
    assert [event["event_type"] for event in recorder.events] == ["graph.completed"]
    assert result["analysis_id"] is not None
    assert result["node_results"][-1].status is NodeStatus.OK
