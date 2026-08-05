"""
Wire-orchestrator shadow tests (TASK-COH-V2-WIRE-ORCHESTRATOR).

Verifies that when coherence_v2_enabled=True and coherence_v2_shadow_mode=True,
POST /evaluate runs the real CoherenceV2Orchestrator — NOT adapt_v1_dashboard —
and emits a coherence.v1_v2_score_delta event with real bottom-up v2 scores.
The returned primary result must remain V1 (no cutover).

Doc fetch is performed via SqlAlchemyDocumentRepository.list_for_project (RLS-safe);
these tests patch the repository, not db.execute, to avoid coupling to internal
query construction.

Refers to Suite ID: TS-UA-COH-V2-WIRE-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.coherence.adapters.persistence.models import CoherenceResultORM, CoherenceV2ShadowORM
from src.coherence.models import (
    CategoryBreakdown,
    Clause,
    CoherenceResult,
    EnrichedCoherenceResult,
    SeverityCount,
)

# Patch path for the repository method — lazy-imported inside the router
_REPO_LIST_FOR_PROJECT = (
    "src.documents.adapters.persistence"
    ".sqlalchemy_document_repository.SqlAlchemyDocumentRepository.list_for_project"
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _clauses() -> list[Clause]:
    return [
        Clause(id="BUD-001", text="Contract value: $1,000,000", data={}),
        Clause(id="SCH-001", text="Delivery deadline: 2025-03-01", data={}),
    ]


@pytest.fixture()
def _v1_result() -> EnrichedCoherenceResult:
    return EnrichedCoherenceResult(
        overall_score=75.0,
        alerts=[],
        category_breakdown=[
            CategoryBreakdown(
                category="financial",
                score=80.0,
                alert_count=0,
                severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0),
                impact_percentage=15.0,
            )
        ],
        calculated_at=datetime.now(UTC),
        finding_signals=[],
        llm_cost_usd=0.0,
    )


@pytest.fixture()
def _current_user() -> SimpleNamespace:
    return SimpleNamespace(tenant_id=uuid4())


def _simple_db() -> Mock:
    """Minimal db mock (router still receives it as a parameter)."""
    mock_db = Mock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    return mock_db


def _doc(doc_type: str) -> SimpleNamespace:
    return SimpleNamespace(document_type=doc_type)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v2_shadow_runs_orchestrator_not_adapter(
    _clauses: list[Clause],
    _v1_result: EnrichedCoherenceResult,
    _current_user: SimpleNamespace,
) -> None:
    """
    With coherence_v2_enabled=True + coherence_v2_shadow_mode=True:
    (a) EvidenceService.collect is invoked for all 6 categories — proves the
        real orchestrator ran, not adapt_v1_dashboard.
    (b) ShadowRunner.emit is called once; delta carries v1 score and v2 status.
    (c) adapt_v1_dashboard is NOT called — shadow uses orchestrator path.
    (d) Returned primary result is still V1 (no cutover).
    (e) Doc fetch goes through SqlAlchemyDocumentRepository, not raw db.execute.
    """
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    project_id = uuid4()
    mock_settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)

    evidence_calls: list[str] = []
    emit_calls: list = []

    # Two docs with typed document_type — contract and schedule
    mock_docs = [_doc("contract"), _doc("schedule")]

    # Spy on EvidenceService.collect — wraps the real (filtering) implementation
    from src.coherence.services.v2.evidence_service import EvidenceService as _EvidSvc

    _real_collect = _EvidSvc.collect

    def _spy_collect(self: _EvidSvc, category: str, project_docs: list) -> object:
        evidence_calls.append(category)
        return _real_collect(self, category, project_docs)

    def _spy_emit(self: object, delta: object, feature_flag_state: object = None) -> None:
        emit_calls.append(delta)

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=_v1_result,
        ),
        patch("src.config.get_settings", return_value=mock_settings),
        patch(
            "src.coherence.services.v2.evidence_service.EvidenceService.collect",
            _spy_collect,
        ),
        patch(
            "src.coherence.services.v2.shadow_runner.ShadowRunner.emit",
            _spy_emit,
        ),
        patch(
            "src.coherence.adapters.v1_to_v2.adapt_v1_dashboard",
        ) as mock_adapter,
        patch(
            _REPO_LIST_FOR_PROJECT,
            new_callable=AsyncMock,
            return_value=(mock_docs, len(mock_docs)),
        ),
    ):
        request = CoherenceEvaluateRequest(
            project_id=project_id,
            clauses=_clauses,
        )
        db = _simple_db()
        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=db,
            current_user=_current_user,
        )

    # (a) Orchestrator called collect for every v2 category
    assert set(evidence_calls) == {
        "SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME",
    }, f"Expected 6 category calls, got: {evidence_calls}"

    # (b) Shadow delta emitted once with real data
    assert len(emit_calls) == 1, "ShadowRunner.emit must be called exactly once"
    delta = emit_calls[0]
    assert delta.coherence_v1_score == _v1_result.overall_score
    assert delta.v2_status is not None  # orchestrator always populates this

    # (c) adapt_v1_dashboard bypassed on the evaluate path
    mock_adapter.assert_not_called()

    # (d) Primary returned score is still V1
    assert isinstance(result, CoherenceResult)
    assert result.overall_score == _v1_result.overall_score

    persisted = [call.args[0] for call in db.add.call_args_list]
    assert len([row for row in persisted if isinstance(row, CoherenceResultORM)]) == 1
    shadows = [row for row in persisted if isinstance(row, CoherenceV2ShadowORM)]
    assert len(shadows) == 1
    assert shadows[0].tenant_id == _current_user.tenant_id
    assert shadows[0].project_id == project_id
    assert shadows[0].score_version == "coherence-v2"
    assert shadows[0].categories_v2
    db.execute.assert_awaited_once()
    assert db.execute.await_args.args[1] == {"tenant_id": str(_current_user.tenant_id)}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v2_shadow_disabled_when_v2_flag_off(
    _clauses: list[Clause],
    _v1_result: EnrichedCoherenceResult,
    _current_user: SimpleNamespace,
) -> None:
    """When coherence_v2_enabled=False (default), shadow must NOT run."""
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    project_id = uuid4()
    emit_calls: list = []

    mock_settings = SimpleNamespace(coherence_v2_enabled=False, coherence_v2_shadow_mode=True)

    def _spy_emit(self: object, delta: object, feature_flag_state: object = None) -> None:
        emit_calls.append(delta)

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=_v1_result,
        ),
        patch("src.config.get_settings", return_value=mock_settings),
        patch(
            "src.coherence.services.v2.shadow_runner.ShadowRunner.emit",
            _spy_emit,
        ),
    ):
        request = CoherenceEvaluateRequest(project_id=project_id, clauses=_clauses)
        db = _simple_db()
        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=db,
            current_user=_current_user,
        )

    assert emit_calls == [], "ShadowRunner.emit must NOT fire when coherence_v2_enabled=False"
    persisted = [call.args[0] for call in db.add.call_args_list]
    assert not any(isinstance(row, CoherenceV2ShadowORM) for row in persisted)
    assert len([row for row in persisted if isinstance(row, CoherenceResultORM)]) == 1
    db.execute.assert_not_awaited()
    assert isinstance(result, CoherenceResult)
    assert result.overall_score == _v1_result.overall_score


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v2_shadow_disabled_when_shadow_mode_flag_off(
    _clauses: list[Clause],
    _v1_result: EnrichedCoherenceResult,
    _current_user: SimpleNamespace,
) -> None:
    """With shadow mode disabled, no v2 row may be written despite v2 being enabled."""
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    project_id = uuid4()
    db = _simple_db()
    mock_settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=False)

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=_v1_result,
        ),
        patch("src.config.get_settings", return_value=mock_settings),
    ):
        result = await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(project_id=project_id, clauses=_clauses),
            include_diagnostics=False,
            db=db,
            current_user=_current_user,
        )

    persisted = [call.args[0] for call in db.add.call_args_list]
    assert not any(isinstance(row, CoherenceV2ShadowORM) for row in persisted)
    assert isinstance(result, CoherenceResult)
    assert result.overall_score == _v1_result.overall_score


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v2_shadow_skipped_without_project_id(
    _clauses: list[Clause],
    _v1_result: EnrichedCoherenceResult,
    _current_user: SimpleNamespace,
) -> None:
    """Without project_id there are no docs to query; shadow must not run."""
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    emit_calls: list = []
    mock_settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)

    def _spy_emit(self: object, delta: object, feature_flag_state: object = None) -> None:
        emit_calls.append(delta)

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=_v1_result,
        ),
        patch("src.config.get_settings", return_value=mock_settings),
        patch(
            "src.coherence.services.v2.shadow_runner.ShadowRunner.emit",
            _spy_emit,
        ),
    ):
        # clauses-only request: no project_id → shadow cannot run
        request = CoherenceEvaluateRequest(clauses=_clauses)
        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=_simple_db(),
            current_user=_current_user,
        )

    assert emit_calls == [], "Shadow must not run when project_id is absent"
    assert isinstance(result, CoherenceResult)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v2_shadow_failure_does_not_break_v1_response(
    _clauses: list[Clause],
    _v1_result: EnrichedCoherenceResult,
    _current_user: SimpleNamespace,
) -> None:
    """If the shadow path raises an exception the V1 result is still returned."""
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    project_id = uuid4()
    mock_settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=_v1_result,
        ),
        patch("src.config.get_settings", return_value=mock_settings),
        # Repo returns one doc; orchestrator crashes after that
        patch(
            _REPO_LIST_FOR_PROJECT,
            new_callable=AsyncMock,
            return_value=([_doc("contract")], 1),
        ),
        patch(
            "src.coherence.services.v2.orchestrator.CoherenceV2Orchestrator.run",
            new_callable=AsyncMock,
            side_effect=RuntimeError("simulated orchestrator crash"),
        ),
    ):
        request = CoherenceEvaluateRequest(project_id=project_id, clauses=_clauses)
        result = await evaluate_project_coherence(
            payload=request,
            include_diagnostics=False,
            db=_simple_db(),
            current_user=_current_user,
        )

    # V1 result must still be returned despite the shadow crash
    assert isinstance(result, CoherenceResult)
    assert result.overall_score == _v1_result.overall_score


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v2_shadow_persist_failure_does_not_break_v1_response(
    _clauses: list[Clause],
    _v1_result: EnrichedCoherenceResult,
    _current_user: SimpleNamespace,
) -> None:
    """A persistence failure is rolled back and leaves the primary v1 response intact."""
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    project_id = uuid4()
    db = _simple_db()
    mock_settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=_v1_result,
        ),
        patch("src.config.get_settings", return_value=mock_settings),
        patch(
            _REPO_LIST_FOR_PROJECT,
            new_callable=AsyncMock,
            return_value=([_doc("contract")], 1),
        ),
        patch(
            "src.coherence.services.v2.shadow_runner.ShadowRunner.persist",
            new_callable=AsyncMock,
            side_effect=RuntimeError("simulated shadow persistence crash"),
        ),
    ):
        result = await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(project_id=project_id, clauses=_clauses),
            include_diagnostics=False,
            db=db,
            current_user=_current_user,
        )

    db.rollback.assert_awaited_once()
    assert isinstance(result, CoherenceResult)
    assert result.overall_score == _v1_result.overall_score
