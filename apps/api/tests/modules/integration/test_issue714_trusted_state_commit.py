"""
C2PRO ISSUE #714 -- TRUSTED-STATE COMMIT ("persisted != trusted").

A HITL-gated analysis is persisted as a PROPOSED candidate bound to its
review. It must not reach the canonical artifact set (the only input of the
canonical ProjectGraph / Health) until the EXACT reviewed candidate (id +
version + digest) is approved through the real route:

    POST /hitl/queue/{id}/approve -> ResumeWorkflowUseCase -> finalize_v3
                                  -> trusted commit -> ProjectGraph enqueue

Adversarial matrix:
  A pending proposal cannot commit       D duplicate approve stays exactly-once
  B reject cannot commit                 E correction commits only Vn+1
  C approve commits once                 F stale/superseded approval fails closed

Everything runs against REAL PostgreSQL, a REAL AsyncPostgresSaver and the
REAL production graph nodes (the #646 / #649 harness).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import Analysis, DocumentArtifactORM
from src.analysis.application import document_artifact_completion
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import (
    REVIEW_BINDING_KEY,
    CandidateBinding,
    StaleCandidateError,
)
from src.core.auth.models import Tenant, User
from src.core.tasks import project_graph_tasks
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ReviewStatus
from src.temporal.application import project_snapshot_trigger
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    _post_approve,
    _post_reject,
    request_sessions,  # noqa: F401 - pytest fixture
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    _arrange,
    _reload,
    independent_sessions,  # noqa: F401 - pytest fixture
    real_saver,  # noqa: F401 - pytest fixture
)

pytestmark = pytest.mark.asyncio


# ── harness ──────────────────────────────────────────────────────────────────


@pytest.fixture
def graph_enqueues(monkeypatch) -> list[tuple[UUID, UUID]]:
    """Every canonical ProjectGraph enqueue, from ANY emitter."""
    calls: list[tuple[UUID, UUID]] = []

    async def _record(*, project_id: UUID, tenant_id: UUID, **_: Any) -> None:
        calls.append((UUID(str(project_id)), UUID(str(tenant_id))))

    monkeypatch.setattr(project_graph_tasks, "enqueue_project_graph", _record)
    monkeypatch.setattr(document_artifact_completion, "enqueue_project_graph", _record)
    monkeypatch.setattr(
        project_snapshot_trigger, "enqueue_project_snapshot", lambda **_: None
    )
    return calls


@pytest.fixture
def completion_sessions(monkeypatch, independent_sessions):  # noqa: F811
    """Drive the REAL completion hook on the test database."""
    maker_holder: dict[str, Any] = {}

    @asynccontextmanager
    async def _raw_session():
        # The hook issues its own SET LOCAL app.current_tenant; the factory
        # needs a tenant for set_config, which the hook overrides.
        async with independent_sessions(maker_holder["tenant"]) as session:
            yield session

    async def _no_init() -> None:
        return None

    monkeypatch.setattr(document_artifact_completion, "get_raw_session", _raw_session)
    monkeypatch.setattr(document_artifact_completion, "init_db", _no_init)
    return maker_holder


def _final_state(arranged: Any, tenant_id: UUID, *, gated: bool, title: str) -> dict[str, Any]:
    return {
        "project_id": str(arranged.project_id),
        "tenant_id": str(tenant_id),
        "document_id": str(arranged.document_id),
        "thread_id": f"document:{arranged.document_id}:analysis",
        "doc_type": "contract",
        "human_approval_required": gated,
        "extracted_risks": [{"title": title, "description": "d", "severity": "HIGH"}],
        "extracted_wbs": [],
        "coherence_score": 60.0,
        "coherence_score_version": "coherence-v1",
    }


async def _propose(completion_sessions, arranged, tenant_id, *, title="AI risk") -> None:
    completion_sessions["tenant"] = tenant_id
    await document_artifact_completion._persist_artifact(
        _final_state(arranged, tenant_id, gated=True, title=title)
    )


async def _rows(sessions, tenant_id: UUID, document_id: UUID) -> list[DocumentArtifactORM]:
    async with sessions(tenant_id) as s:
        return list(
            (
                await s.execute(
                    select(DocumentArtifactORM)
                    .where(DocumentArtifactORM.document_id == document_id)
                    .order_by(DocumentArtifactORM.artifact_version)
                )
            )
            .scalars()
            .all()
        )


async def _canonical(sessions, tenant_id: UUID, project_id: UUID) -> list[DocumentArtifact]:
    async with sessions(tenant_id) as s:
        return await SqlAlchemyDocumentArtifactRepository(s).list_trusted_for_project(
            project_id=project_id, tenant_id=tenant_id
        )


async def _binding(db: AsyncSession, review_row_id: UUID) -> CandidateBinding | None:
    review = await _reload(db, ReviewItemORM, review_row_id)
    return CandidateBinding.from_json((review.review_metadata or {}).get(REVIEW_BINDING_KEY))


async def _seed_trusted(sessions, arranged, tenant_id: UUID, title: str) -> None:
    async with sessions(tenant_id) as s:
        await SqlAlchemyDocumentArtifactRepository(s).save(
            DocumentArtifact(
                document_id=str(arranged.document_id),
                doc_type="contract",
                extracted_risks=[RiskItem(title=title, description="d")],
            ),
            project_id=arranged.project_id,
            tenant_id=tenant_id,
        )


def _titles(artifacts: list[DocumentArtifact]) -> list[str]:
    return [risk.title for a in artifacts for risk in a.extracted_risks]


# ── 1 / A: a pending proposal persists but is never canonical ────────────────


async def test_a_pending_candidate_persists_but_cannot_commit(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)

    await _propose(completion_sessions, arranged, tenant.id)

    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.trust_state, r.artifact_version) for r in rows] == [("proposed", 1)]
    assert rows[0].artifact_hash and len(rows[0].artifact_hash) == 64
    assert rows[0].scoring == {"coherence_score": 60.0, "score_version": "coherence-v1"}
    binding = await _binding(db, arranged.review_row_id)
    assert binding == CandidateBinding(
        rows[0].artifact_id, arranged.document_id, 1, rows[0].artifact_hash
    )
    assert await _canonical(independent_sessions, tenant.id, arranged.project_id) == []
    assert graph_enqueues == [], "a PROPOSED candidate must never reach ProjectGraph"

    # Substituted content under the same id/version cannot be committed.
    forged = CandidateBinding(binding.artifact_id, binding.document_id, 1, "0" * 64)
    with pytest.raises(StaleCandidateError):
        async with independent_sessions(tenant.id) as s:
            await SqlAlchemyDocumentArtifactRepository(s).commit_candidate(
                forged, tenant_id=tenant.id
            )
    assert await _canonical(independent_sessions, tenant.id, arranged.project_id) == []


# ── 2 / B: reject keeps the prior trusted state authoritative ────────────────


async def test_b_reject_cannot_commit_and_keeps_prior_trusted_state(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _seed_trusted(independent_sessions, arranged, tenant.id, "Prior trusted risk")
    await _propose(completion_sessions, arranged, tenant.id, title="Proposed risk")

    response = await _post_reject(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    assert response.current_status == ReviewStatus.REJECTED
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state) for r in rows] == [
        (1, "trusted"),
        (2, "rejected"),
    ], "the rejected candidate stays as immutable audit evidence"
    canonical = await _canonical(independent_sessions, tenant.id, arranged.project_id)
    assert _titles(canonical) == ["Prior trusted risk"]
    assert graph_enqueues == []

    with pytest.raises(StaleCandidateError):
        async with independent_sessions(tenant.id) as s:
            await SqlAlchemyDocumentArtifactRepository(s).commit_candidate(
                CandidateBinding(
                    rows[1].artifact_id, arranged.document_id, 2, rows[1].artifact_hash
                ),
                tenant_id=tenant.id,
            )


# ── 3 / C + D: approve commits exactly the candidate, exactly once ───────────


async def test_c_approve_commits_exact_candidate_and_enqueues_once(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _seed_trusted(independent_sessions, arranged, tenant.id, "Prior trusted risk")
    await _propose(completion_sessions, arranged, tenant.id, title="Reviewed risk")

    response = await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    assert response.current_status == ReviewStatus.APPROVED
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state, r.lifecycle_status) for r in rows] == [
        (1, "trusted", "superseded"),
        (2, "trusted", "active"),
    ]
    canonical = await _canonical(independent_sessions, tenant.id, arranged.project_id)
    assert _titles(canonical) == ["Reviewed risk"]
    assert graph_enqueues == [(arranged.project_id, tenant.id)]


async def test_d_duplicate_and_concurrent_approve_commit_once(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)

    def approve() -> Any:
        return _post_approve(
            request_sessions, tenant.id, arranged.review_item_id,
            saver=saver, app=arranged.app, sessions=independent_sessions,
        )

    await asyncio.gather(*[approve() for _ in range(3)], return_exceptions=True)
    for _ in range(2):  # double click after the decision committed
        await approve()

    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.trust_state, r.lifecycle_status) for r in rows] == [("trusted", "active")]
    assert graph_enqueues == [(arranged.project_id, tenant.id)], (
        f"exactly one canonical commit/enqueue, got {graph_enqueues}"
    )
    # A re-delivered commit of the same exact candidate is a no-op.
    binding = await _binding(db, arranged.review_row_id)
    async with independent_sessions(tenant.id) as s:
        again = await SqlAlchemyDocumentArtifactRepository(s).commit_candidate(
            binding, tenant_id=tenant.id
        )
    assert again.outcome.value == "already_trusted"


# ── 5 / E: correction supersedes Vn; approval binds and commits Vn+1 ─────────


async def test_e_corrected_proposal_commits_only_corrected_version(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id, title="AI wrong risk")
    original = await _binding(db, arranged.review_row_id)

    async with independent_sessions(tenant.id) as s:
        corrected = await SqlAlchemyDocumentArtifactRepository(s).propose_correction(
            original,
            DocumentArtifact(
                document_id=str(arranged.document_id),
                doc_type="contract",
                extracted_risks=[RiskItem(title="Human corrected risk", description="d")],
            ),
            tenant_id=tenant.id,
            review_row_id=arranged.review_row_id,
        )

    assert corrected.artifact_version == original.artifact_version + 1
    assert await _binding(db, arranged.review_row_id) == corrected
    # Vn can never be committed once superseded.
    with pytest.raises(StaleCandidateError):
        async with independent_sessions(tenant.id) as s:
            await SqlAlchemyDocumentArtifactRepository(s).commit_candidate(
                original, tenant_id=tenant.id
            )
    assert await _canonical(independent_sessions, tenant.id, arranged.project_id) == []

    await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state) for r in rows] == [
        (1, "superseded"),
        (2, "trusted"),
    ]
    canonical = await _canonical(independent_sessions, tenant.id, arranged.project_id)
    assert _titles(canonical) == ["Human corrected risk"]
    assert graph_enqueues == [(arranged.project_id, tenant.id)]


# ── 6 / F: a stale/superseded approval fails closed ──────────────────────────


async def test_f_stale_approval_after_reanalysis_fails_closed(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id, title="Reviewed v1")
    reviewed = await _binding(db, arranged.review_row_id)

    # A re-analysis on the SAME (stable) thread lands while the human is
    # still looking at v1. It must not silently rebind the review.
    await _propose(completion_sessions, arranged, tenant.id, title="Unreviewed v2")
    assert await _binding(db, arranged.review_row_id) == reviewed

    with pytest.raises(HTTPException):
        await _post_approve(
            request_sessions, tenant.id, arranged.review_item_id,
            saver=saver, app=arranged.app, sessions=independent_sessions,
        )

    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert review.current_status != ReviewStatus.APPROVED, "decision rolled back"
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state) for r in rows] == [
        (1, "superseded"),
        (2, "proposed"),
    ]
    assert await _canonical(independent_sessions, tenant.id, arranged.project_id) == []
    assert graph_enqueues == []
    # Refused BEFORE the graph resumed: no analysis feeds the trusted score.
    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == arranged.project_id))
    ).scalars().all()
    assert analyses == [], "a stale approval must not reach N17"


async def test_non_gated_completion_is_trusted_and_enqueues_once(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    completion_sessions["tenant"] = tenant.id

    await document_artifact_completion._persist_artifact(
        _final_state(arranged, tenant.id, gated=False, title="Auto-trusted risk")
    )

    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.trust_state, r.lifecycle_status) for r in rows] == [("trusted", "active")]
    assert graph_enqueues == [(arranged.project_id, tenant.id)]



# ── Coherence: trusted vs projected through the real dashboard endpoint ─────


async def _dashboard(maker, tenant_id: UUID, project_id: UUID) -> Any:
    """GET /coherence/dashboard/{project_id} on a fresh request session.

    A fresh session per call is also the reload/relogin case: nothing is
    cached between reads, so the state shown is the durable state.
    """
    from types import SimpleNamespace

    from sqlalchemy import text as sql_text

    from src.coherence.router import get_coherence_dashboard

    async with maker() as session:
        await session.execute(
            sql_text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        return await get_coherence_dashboard(
            project_id=project_id,
            current_user=SimpleNamespace(tenant_id=tenant_id),
            db=session,
            flags_service=None,
        )


async def test_dashboard_trusted_ignores_pending_and_projection_uses_it(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)

    empty = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    assert empty.trusted_score is None, "no trusted evidence -> null, never 0"
    assert (empty.projected_score, empty.pending_review_count) == (None, 0)
    assert empty.projection_status == "none"

    await _propose(completion_sessions, arranged, tenant.id)  # engine score 60, v1
    pending = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    assert pending.coherence_score is None and pending.trusted_score is None
    assert pending.projected_score == 60.0
    assert pending.projected_delta is None
    assert pending.pending_review_count == 1
    assert pending.projection_status == "provisional"
    assert pending.projection_score_version == "coherence-v1"

    # reload/relogin: a brand-new session sees the identical durable state.
    again = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    assert again.model_dump(exclude={"last_updated"}) == pending.model_dump(
        exclude={"last_updated"}
    )

    await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )
    approved = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    # The trusted score is RECOMPUTED by the pipeline (N17 persists the
    # resumed run's engine output: 90 in this harness), not copied from
    # the projection (60).
    assert approved.trusted_score == approved.coherence_score == 90
    assert approved.projected_score is None
    assert approved.pending_review_count == 0
    assert approved.projection_status == "none"


async def test_dashboard_reject_removes_candidate_from_projection(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)
    assert (await _dashboard(request_sessions, tenant.id, arranged.project_id)).projected_score == 60.0

    await _post_reject(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    after = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    assert after.trusted_score is None, "reject leaves no trusted evidence"
    assert after.projected_score is None
    assert after.pending_review_count == 0


async def test_dashboard_correction_replaces_candidate_in_projection(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    from src.analysis.domain.trust import CandidateScoring

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)
    original = await _binding(db, arranged.review_row_id)

    async with independent_sessions(tenant.id) as s:
        await SqlAlchemyDocumentArtifactRepository(s).propose_correction(
            original,
            DocumentArtifact(document_id=str(arranged.document_id), doc_type="contract"),
            tenant_id=tenant.id,
            review_row_id=arranged.review_row_id,
            scoring=CandidateScoring(coherence_score=75.0, score_version="coherence-v1"),
        )

    view = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    assert view.pending_review_count == 1, "Vn+1 replaces Vn; it does not stack"
    assert view.projected_score == 75.0


# ── P0 race: a decision before the candidate is persisted/bound ─────────────


async def _operations(sessions, tenant_id: UUID, project_id: UUID) -> int:
    from sqlalchemy import text as sql_text

    async with sessions(tenant_id) as s:
        return int(
            (
                await s.execute(
                    sql_text(
                        "SELECT count(*) FROM resume_operations "
                        "WHERE project_id = cast(:p as uuid)"
                    ),
                    {"p": str(project_id)},
                )
            ).scalar_one()
        )


async def _decision_ready(db: AsyncSession, tenant_id: UUID, review_row_id: UUID) -> bool:
    from src.modules.hitl.adapters.http.router import _to_review_item_response
    from src.modules.hitl.adapters.persistence.repository import (
        SqlAlchemyReviewQueueRepository,
    )

    await _reload(db, ReviewItemORM, review_row_id)
    item = await SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id).get_review_item(
        review_row_id
    )
    assert item is not None
    return _to_review_item_response(item).decision_ready


async def test_decision_before_candidate_binding_fails_closed_then_succeeds_once(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    from tests.modules.integration.test_p0b_crash_safe_resume_recovery import N17_RUNS

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    # The real N13 created and exposed the review; the completion hook has
    # NOT yet persisted/bound the candidate.
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    N17_RUNS.clear()
    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert review.review_metadata.get("trust_candidate_required") is True
    assert await _decision_ready(db, tenant.id, arranged.review_row_id) is False

    for decide in (_post_approve, _post_reject):
        with pytest.raises(HTTPException) as refused:
            await decide(
                request_sessions, tenant.id, arranged.review_item_id,
                saver=saver, app=arranged.app, sessions=independent_sessions,
            )
        assert refused.value.status_code == 400
        assert "not ready" in str(refused.value.detail)

    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert review.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED, "no decision"
    assert await _operations(independent_sessions, tenant.id, arranged.project_id) == 0
    assert N17_RUNS == [], "no graph ran"
    assert graph_enqueues == []

    # The completion hook lands: persist + bind the exact candidate.
    await _propose(completion_sessions, arranged, tenant.id, title="Bound risk")
    assert await _decision_ready(db, tenant.id, arranged.review_row_id) is True

    await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )
    await _post_approve(  # double click after the decision committed
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert review.current_status == ReviewStatus.APPROVED
    assert await _operations(independent_sessions, tenant.id, arranged.project_id) == 1
    assert len(N17_RUNS) == 1
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.trust_state, r.lifecycle_status) for r in rows] == [("trusted", "active")]
    assert graph_enqueues == [(arranged.project_id, tenant.id)]


async def test_reject_after_candidate_binding_succeeds(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    with pytest.raises(HTTPException):
        await _post_reject(
            request_sessions, tenant.id, arranged.review_item_id,
            saver=saver, app=arranged.app, sessions=independent_sessions,
        )
    await _propose(completion_sessions, arranged, tenant.id)

    response = await _post_reject(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    assert response.current_status == ReviewStatus.REJECTED
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [r.trust_state for r in rows] == ["rejected"]
    assert graph_enqueues == []


async def test_legacy_review_without_marker_stays_decidable(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Pre-#714 reviews carry no marker and no candidate: unchanged behaviour."""
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    review.review_metadata = {
        k: v for k, v in review.review_metadata.items() if k != "trust_candidate_required"
    }
    await db.commit()
    assert await _decision_ready(db, tenant.id, arranged.review_row_id) is True

    response = await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    assert response.current_status == ReviewStatus.APPROVED
    assert graph_enqueues == [], "nothing was proposed, so nothing becomes trusted"


async def test_escalated_review_is_decidable_through_the_fenced_path(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)
    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    review.current_status = ReviewStatus.ESCALATED  # SLA job escalated it
    await db.commit()

    response = await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )

    assert response.current_status == ReviewStatus.APPROVED
    assert await _operations(independent_sessions, tenant.id, arranged.project_id) == 1
    assert graph_enqueues == [(arranged.project_id, tenant.id)]
