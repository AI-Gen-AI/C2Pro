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


_CATEGORIES = ("LEGAL", "TECHNICAL", "SCOPE", "BUDGET", "TIME", "QUALITY")


def _risks(title: str, level: str = "HIGH") -> list[dict[str, str]]:
    """Impact-bearing risks across all six categories, so the canonical
    evaluator produces a real score; the first risk carries ``title``."""
    return [
        {
            "title": title if i == 0 else f"{title}:{category}",
            "description": "d",
            "category": category,
            "impact": level,
            "likelihood": level,
        }
        for i, category in enumerate(_CATEGORIES)
    ]


async def _expected_projection(project_id: UUID, tenant_id: UUID, artifacts) -> float | None:
    from src.analysis.adapters.graph.project_graph import evaluate_artifact_set

    result = await evaluate_artifact_set(
        artifacts, project_id=project_id, tenant_id=tenant_id, llm_on=False
    )
    return result.summary.overall_score


def _final_state(arranged: Any, tenant_id: UUID, *, gated: bool, title: str) -> dict[str, Any]:
    return {
        "project_id": str(arranged.project_id),
        "tenant_id": str(tenant_id),
        "document_id": str(arranged.document_id),
        "thread_id": f"document:{arranged.document_id}:analysis",
        "doc_type": "contract",
        "human_approval_required": gated,
        "extracted_risks": _risks(title),
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
    return [a.extracted_risks[0].title for a in artifacts if a.extracted_risks]


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


async def _review_rows(db: AsyncSession, document_id: UUID) -> list[ReviewItemORM]:
    return list(
        (
            await db.execute(
                select(ReviewItemORM)
                .where(ReviewItemORM.item_id == document_id)
                .order_by(ReviewItemORM.created_at)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )


async def test_f_stale_decision_after_reanalysis_fails_closed_and_new_review_binds_v2(
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

    # A gated re-analysis on the SAME (stable) thread lands while the human
    # is still looking at v1. It must not silently rebind that review: the
    # old review is closed and a NEW review is bound to exactly v2.
    await _propose(completion_sessions, arranged, tenant.id, title="Unreviewed v2")

    old = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert old.current_status == ReviewStatus.CLOSED
    assert CandidateBinding.from_json(old.review_metadata["candidate_binding"]) == reviewed
    assert old.review_metadata["closed_reason"] == "candidate_superseded"
    reviews = await _review_rows(db, arranged.document_id)
    assert len(reviews) == 2
    new = reviews[-1]
    assert new.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state) for r in rows] == [
        (1, "superseded"),
        (2, "proposed"),
    ]
    assert CandidateBinding.from_json(new.review_metadata["candidate_binding"]) == (
        CandidateBinding(rows[1].artifact_id, arranged.document_id, 2, rows[1].artifact_hash)
    )
    assert new.review_metadata["supersedes_review_id"] == str(old.id)

    # Deciding the OLD review exactly (by its row id) fails closed, both ways.
    for decide in (_post_approve, _post_reject):
        with pytest.raises(HTTPException):
            await decide(
                request_sessions, tenant.id, arranged.review_row_id,
                saver=saver, app=arranged.app, sessions=independent_sessions,
            )
    assert await _canonical(independent_sessions, tenant.id, arranged.project_id) == []
    assert graph_enqueues == []
    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == arranged.project_id))
    ).scalars().all()
    assert analyses == [], "a stale decision must not reach N17"

    # The new review commits exactly v2.
    await _post_approve(
        request_sessions, tenant.id, new.id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state) for r in rows] == [
        (1, "superseded"),
        (2, "trusted"),
    ]
    assert _titles(await _canonical(independent_sessions, tenant.id, arranged.project_id)) == [
        "Unreviewed v2"
    ]
    assert graph_enqueues == [(arranged.project_id, tenant.id)]


async def test_newer_trusted_completion_retires_bound_proposal(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """V1 trusted -> V2 proposed+bound -> newer non-gated V3 trusted: V2 can
    never be approved over V3; V3 stays the sole canonical artifact."""
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _seed_trusted(independent_sessions, arranged, tenant.id, "V1")
    await _propose(completion_sessions, arranged, tenant.id, title="V2 proposal")
    stale = await _binding(db, arranged.review_row_id)
    completion_sessions["tenant"] = tenant.id
    await document_artifact_completion._persist_artifact(
        _final_state(arranged, tenant.id, gated=False, title="V3 newer")
    )

    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state, r.lifecycle_status) for r in rows] == [
        (1, "trusted", "superseded"),
        (2, "superseded", "superseded"),
        (3, "trusted", "active"),
    ]
    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert review.current_status == ReviewStatus.CLOSED

    with pytest.raises(HTTPException):
        await _post_approve(
            request_sessions, tenant.id, arranged.review_row_id,
            saver=saver, app=arranged.app, sessions=independent_sessions,
        )
    with pytest.raises(StaleCandidateError):
        async with independent_sessions(tenant.id) as s:
            await SqlAlchemyDocumentArtifactRepository(s).commit_candidate(
                stale, tenant_id=tenant.id
            )
    assert _titles(await _canonical(independent_sessions, tenant.id, arranged.project_id)) == [
        "V3 newer"
    ]
    assert graph_enqueues == [(arranged.project_id, tenant.id)], "only V3's completion"


async def test_reject_is_exact_binding_and_stale_reject_fails_closed(
    independent_sessions,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    real_saver,  # noqa: F811
    completion_sessions,
    graph_enqueues,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)
    bound = await _binding(db, arranged.review_row_id)

    forged = CandidateBinding(bound.artifact_id, bound.document_id, 1, "0" * 64)
    with pytest.raises(StaleCandidateError):
        async with independent_sessions(tenant.id) as s:
            await SqlAlchemyDocumentArtifactRepository(s).reject_candidate(
                forged, tenant_id=tenant.id
            )
    # Superseded (e.g. by a correction) -> rejecting the old version fails.
    async with independent_sessions(tenant.id) as s:
        await SqlAlchemyDocumentArtifactRepository(s).propose_correction(
            bound,
            DocumentArtifact(document_id=str(arranged.document_id), doc_type="contract"),
            tenant_id=tenant.id,
            review_row_id=arranged.review_row_id,
        )
    with pytest.raises(StaleCandidateError):
        async with independent_sessions(tenant.id) as s:
            await SqlAlchemyDocumentArtifactRepository(s).reject_candidate(
                bound, tenant_id=tenant.id
            )
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.artifact_version, r.trust_state) for r in rows] == [
        (1, "superseded"),
        (2, "proposed"),
    ], "the stale rejection neither rejected nor touched the current proposal"


async def test_pending_count_and_projection_use_only_actionable_bound_proposals(
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
    # An orphan PROPOSED row for another document, with no review at all.
    from uuid import uuid4

    from src.analysis.domain.trust import TrustState

    async with independent_sessions(tenant.id) as s:
        await SqlAlchemyDocumentArtifactRepository(s)._insert(
            DocumentArtifact(document_id=str(uuid4()), doc_type="contract"),
            project_id=arranged.project_id,
            tenant_id=tenant.id,
            trust_state=TrustState.PROPOSED,
            scoring=None,
        )
    async with independent_sessions(tenant.id) as s:
        pending = await SqlAlchemyDocumentArtifactRepository(s).list_pending_candidates(
            project_id=arranged.project_id, tenant_id=tenant.id
        )
    assert [p.binding.document_id for p in pending] == [arranged.document_id]
    assert pending[0].review_row_id == arranged.review_row_id


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
    async with independent_sessions(tenant.id) as s:
        candidates = await SqlAlchemyDocumentArtifactRepository(s).list_pending_candidates(
            project_id=arranged.project_id, tenant_id=tenant.id
        )
    expected = await _expected_projection(
        arranged.project_id, tenant.id, [candidates[0].artifact]
    )
    assert expected is not None
    assert pending.projected_score == expected, "canonical evaluation, not a stored score"
    assert pending.projection_baseline_score is None, "nothing trusted yet"
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
    assert (await _dashboard(request_sessions, tenant.id, arranged.project_id)).projected_score is not None

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

    corrected = DocumentArtifact.model_validate(
        {
            "document_id": str(arranged.document_id),
            "doc_type": "contract",
            "extracted_risks": _risks("Corrected", level="LOW"),
        }
    )
    before = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    async with independent_sessions(tenant.id) as s:
        await SqlAlchemyDocumentArtifactRepository(s).propose_correction(
            original,
            corrected,
            tenant_id=tenant.id,
            review_row_id=arranged.review_row_id,
            scoring=CandidateScoring(coherence_score=75.0, score_version="coherence-v1"),
        )

    view = await _dashboard(request_sessions, tenant.id, arranged.project_id)
    assert view.pending_review_count == 1, "Vn+1 replaces Vn; it does not stack"
    assert view.projected_score == await _expected_projection(
        arranged.project_id, tenant.id, [corrected]
    )
    assert view.projected_score != before.projected_score, "the corrected version is projected"
    assert view.projected_score != 75.0, "stored per-run scores are never used"


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


async def test_gated_candidate_without_any_review_gets_an_actionable_review(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """HITL routing degraded at N13 (no review row): the proposal must not be
    orphaned -- a minimal pending review bound to it is opened."""
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await db.delete(await _reload(db, ReviewItemORM, arranged.review_row_id))
    await db.commit()

    await _propose(completion_sessions, arranged, tenant.id)

    reviews = await _review_rows(db, arranged.document_id)
    assert len(reviews) == 1
    review = reviews[0]
    assert review.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED
    assert review.review_metadata["trust_candidate_required"] is True
    assert review.thread_id == f"document:{arranged.document_id}:analysis"
    rows = await _rows(independent_sessions, tenant.id, arranged.document_id)
    assert CandidateBinding.from_json(review.review_metadata["candidate_binding"]) == (
        CandidateBinding(rows[0].artifact_id, arranged.document_id, 1, rows[0].artifact_hash)
    )
    assert graph_enqueues == []


# ── E: durable trusted -> ProjectGraph hand-off ──────────────────────────────


async def _obligations(sessions, tenant_id: UUID, project_id: UUID) -> list[Any]:
    from sqlalchemy import text as sql_text

    async with sessions(tenant_id) as s:
        return list(
            (
                await s.execute(
                    sql_text(
                        "SELECT artifact_id, artifact_version, projection_state, "
                        "enqueue_attempts FROM system_recovery.trusted_projection_index "
                        "WHERE project_id = cast(:p as uuid) ORDER BY artifact_version"
                    ),
                    {"p": str(project_id)},
                )
            ).all()
        )


async def _clear_obligations(sessions, tenant_id: UUID) -> None:
    from sqlalchemy import text as sql_text

    async with sessions(tenant_id) as s:
        await s.execute(sql_text("DELETE FROM system_recovery.trusted_projection_index"))


async def _run_graph(sessions, tenant_id: UUID, project_id: UUID, monkeypatch) -> dict:
    class _FakeGraph:
        async def ainvoke(self, _state):
            return {"node_results": []}

    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: _FakeGraph())
    async with sessions(tenant_id) as s:
        return await project_graph_tasks.run_project_graph_once(
            project_id=project_id,
            tenant_id=tenant_id,
            artifact_repository=SqlAlchemyDocumentArtifactRepository(s),
        )


async def test_trusted_commit_obligation_is_acknowledged_only_by_a_completed_graph_run(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    await _clear_obligations(independent_sessions, tenant.id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)
    assert await _obligations(independent_sessions, tenant.id, arranged.project_id) == [], (
        "a PROPOSED candidate creates no projection obligation"
    )

    await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )
    [obligation] = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert obligation.projection_state == "pending", "written WITH the trusted commit"

    result = await _run_graph(independent_sessions, tenant.id, arranged.project_id, monkeypatch)
    assert result["projected_obligations"] == 1
    [obligation] = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert obligation.projection_state == "projected"


async def test_lost_enqueue_is_repaired_by_the_reconciler_without_new_activity(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,  # noqa: F811
    completion_sessions,
    db: AsyncSession,
    test_user: User,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    await _clear_obligations(independent_sessions, tenant.id)
    monkeypatch.setattr(project_snapshot_trigger, "enqueue_project_snapshot", lambda **_: None)

    async def broker_down(**_kwargs):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(project_graph_tasks, "enqueue_project_graph", broker_down)
    monkeypatch.setattr(document_artifact_completion, "enqueue_project_graph", broker_down)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id)

    response = await _post_approve(
        request_sessions, tenant.id, arranged.review_item_id,
        saver=saver, app=arranged.app, sessions=independent_sessions,
    )
    assert response.current_status == ReviewStatus.APPROVED, "trusted commit never rolls back"
    assert _titles(await _canonical(independent_sessions, tenant.id, arranged.project_id))
    [obligation] = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert obligation.projection_state == "pending", "the lost dispatch left durable evidence"

    # No further document activity. The beat reconciler repairs it.
    enqueued: list[tuple[UUID, UUID]] = []

    async def record(*, project_id, tenant_id, **_):
        enqueued.append((UUID(str(project_id)), UUID(str(tenant_id))))

    async def enabled(_tenant_id):
        return True

    monkeypatch.setattr(project_graph_tasks, "enqueue_project_graph", record)
    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", enabled)
    counts = await project_graph_tasks.reconcile_trusted_projections(grace_seconds=0)
    assert enqueued == [(arranged.project_id, tenant.id)]
    assert counts["enqueued"] == 1
    [obligation] = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert (obligation.projection_state, obligation.enqueue_attempts) == ("pending", 1)

    await _run_graph(independent_sessions, tenant.id, arranged.project_id, monkeypatch)
    enqueued.clear()
    counts = await project_graph_tasks.reconcile_trusted_projections(grace_seconds=0)
    assert enqueued == [], "a projected obligation is never re-dispatched"
    [obligation] = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert obligation.projection_state == "projected"


async def test_reconciler_never_marks_flag_disabled_tenants_projected(
    independent_sessions,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    real_saver,  # noqa: F811
    completion_sessions,
    graph_enqueues,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    await _clear_obligations(independent_sessions, tenant.id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    completion_sessions["tenant"] = tenant.id
    await document_artifact_completion._persist_artifact(
        _final_state(arranged, tenant.id, gated=False, title="Trusted")
    )

    async def disabled(_tenant_id):
        return False

    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", disabled)
    graph_enqueues.clear()
    counts = await project_graph_tasks.reconcile_trusted_projections(grace_seconds=0)
    assert counts["flag_disabled"] >= 1
    assert graph_enqueues == []
    [obligation] = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert (obligation.projection_state, obligation.enqueue_attempts) == ("pending", 0)


async def test_older_projection_cannot_acknowledge_a_newer_trusted_version(
    independent_sessions,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    real_saver,  # noqa: F811
    completion_sessions,
    graph_enqueues,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    await _clear_obligations(independent_sessions, tenant.id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    completion_sessions["tenant"] = tenant.id
    await document_artifact_completion._persist_artifact(
        _final_state(arranged, tenant.id, gated=False, title="V1")
    )

    # An (older) ProjectGraph run loads V1 ...
    async with independent_sessions(tenant.id) as old_run:
        old_repo = SqlAlchemyDocumentArtifactRepository(old_run)
        await old_repo.list_trusted_for_project(
            project_id=arranged.project_id, tenant_id=tenant.id
        )
        # ... meanwhile V2 becomes trusted (its obligation obsoletes V1's).
        await document_artifact_completion._persist_artifact(
            _final_state(arranged, tenant.id, gated=False, title="V2")
        )
        acknowledged = await old_repo.mark_loaded_projected(
            project_id=arranged.project_id, tenant_id=tenant.id
        )

    assert acknowledged == 0
    rows = await _obligations(independent_sessions, tenant.id, arranged.project_id)
    assert [(r.artifact_version, r.projection_state) for r in rows] == [
        (1, "obsolete"),
        (2, "pending"),
    ], "V2 stays pending until a run that actually loaded V2 completes"
