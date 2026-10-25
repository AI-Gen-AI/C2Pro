"""ACC-01 S5: human decisions are individual, provisional and separate from the final approval.

REAL PostgreSQL, a REAL ``.docx`` contract uploaded and ingested by the real worker (so the
document has a real revision, #711 processing authority and #758 checkpoint lineage), the REAL
``_run_document_analysis`` driving a REAL compiled LangGraph that really interrupts at the
mandatory human review, and the REAL ``/hitl/queue/{id}/approve|reject`` route handlers resuming
that checkpoint. Only the AI provider is absent: the analysis candidate is persisted exactly the
way ``document_artifact_completion`` persists it (a PROPOSED artifact bound to the review), with
risks, because the deterministic provider extracts none.

What is differentiated, and proven here:

* an INDIVIDUAL decision (``CONFIRMED`` / ``DISMISSED`` / ... on one finding) is an append-only
  ledger event. It never approves, rejects or trusts the candidate: the review stays pending, the
  artifact stays PROPOSED and nothing becomes canonical;
* the FINAL approval is a separate act through the review route; only then does the exact
  candidate become TRUSTED, and from that moment no further finding decision is accepted;
* a REJECTION needs a reason, at the HTTP boundary, on both routes that can reject.

Negatives: contradictory (concurrent) decisions, duplicate decisions and approvals, another
tenant, a stale candidate or authority, and every attempt to reach a final state without the
route (wrong role, unbound finding, direct SQL against the ledger).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import TrustState
from src.core.auth.models import UserRole
from src.core.tasks import ingestion_tasks
from src.documents.domain.models import DocumentType
from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    FindingDecisionIdempotencyConflict,
    FindingDecisionIdentityError,
    FindingDecisionRevisionConflict,
)
from src.modules.hitl.application.finding_review_authorization import (
    FindingDecisionSubmission,
    FindingReviewerNotAuthorized,
)
from src.modules.hitl.application.record_finding_decision_use_case import (
    RecordFindingDecisionUseCase,
)
from src.modules.hitl.domain.entities import ReviewStatus
from src.modules.hitl.domain.finding_decision import FindingDecisionAction
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id
from tests.integration.document_flow import (
    test_758_checkpoint_lineage_authority_fence as lineage_harness,
)
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (
    _clean_recovery_discovery_rows,  # noqa: F401  (autouse fixture)
    _RealGraphWorker,
    _review,
    real_saver,  # noqa: F401  (pytest fixture)
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    COMPLETION_CLAUSE,
    PRICE_CLAUSE,
    _docx,
    _project,
    _upload_and_ingest,
    worker,  # noqa: F401  (pytest fixture)
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    _post_approve,
    _post_reject,
    request_sessions,  # noqa: F401  (pytest fixture)
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio

RISKS = [
    {
        "title": "Late completion penalty",
        "description": "Penalty applies after 30/06/2027",
        "category": "TIME",
    },
    {
        "title": "Price revision clause",
        "description": "Price may be revised after approval",
        "category": "BUDGET",
    },
]


# ── the world: a document whose analysis is waiting for a human ─────────────


def _build_graph_with_durable_persistence(saver: Any) -> Any:
    """entry -> REAL human_interrupt_node -> REAL N17 (save_to_db) -> END.

    The #758 harness graph ends in a no-op after the gate. An approval is only a real approval
    when the resumed graph reaches durable persistence (the use case refuses a resume that does
    not), so the harness graph is given the production persistence node instead.
    """
    from langgraph.graph import END, StateGraph  # noqa: PLC0415

    from src.analysis.adapters.graph.nodes import (  # noqa: PLC0415
        human_interrupt_node,
        route_after_human_interrupt,
        save_to_db_node,
    )
    from src.analysis.adapters.graph.schema import ProjectState  # noqa: PLC0415

    async def entry(state: ProjectState) -> ProjectState:
        state["human_approval_required"] = True
        return state

    graph = StateGraph(ProjectState)
    graph.add_node("entry", entry)
    graph.add_node("human_interrupt", human_interrupt_node)
    graph.add_node("save_to_db", save_to_db_node)
    graph.set_entry_point("entry")
    graph.add_edge("entry", "human_interrupt")
    graph.add_conditional_edges(
        "human_interrupt",
        route_after_human_interrupt,
        {"enrichment_dispatch": "save_to_db", "terminated": END},
    )
    graph.add_edge("save_to_db", END)
    return graph.compile(checkpointer=saver)


async def _apply_finding_ledger_schema(db: AsyncSession) -> None:
    """The ledger exists only as a migration (not in the ORM metadata): apply it as the migration does."""
    path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "20261008_0001_hitl_finding_decisions.py"
    )
    spec = importlib.util.spec_from_file_location("hitl_finding_decisions_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connection = await db.connection()
    for statement in module.UPGRADE_STATEMENTS:
        await connection.exec_driver_sql(statement)
    await db.commit()


@pytest.fixture
async def world(
    db: AsyncSession,
    test_user: Any,
    worker: Any,  # noqa: F811
    real_saver: Any,  # noqa: F811
    independent_sessions: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        lineage_harness, "_build_interrupting_graph", _build_graph_with_durable_persistence
    )
    saver, register = real_saver
    await _apply_finding_ledger_schema(db)

    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    document, revision = await _upload_and_ingest(
        db,
        worker,
        test_user,
        project_id,
        filename="contract.docx",
        content=_docx([PRICE_CLAUSE, COMPLETION_CLAUSE]),
        document_type=DocumentType.CONTRACT,
    )
    graph = _RealGraphWorker("A", saver, register)
    outcome = await ingestion_tasks._run_document_analysis(
        tenant_id=tenant_id, document_id=document.id, orchestrator=graph
    )
    assert outcome["status"] == "waiting_for_review", outcome

    [review] = await _review(db, document.id)
    async with independent_sessions(tenant_id) as session:
        await SqlAlchemyDocumentArtifactRepository(session).save(
            DocumentArtifact(
                document_id=str(document.id),
                document_revision_id=str(revision.revision_id),
                doc_type="contract",
                extracted_risks=[RiskItem(**risk) for risk in RISKS],
            ),
            project_id=project_id,
            tenant_id=tenant_id,
            trust_state=TrustState.PROPOSED,
            scoring=None,
            review_thread_id=str(review.thread_id),
        )

    artifact = (
        await db.execute(
            text(
                "SELECT artifact_id, artifact_version, artifact_hash, payload FROM document_artifacts "
                "WHERE document_id = :d AND trust_state = 'proposed'"
            ),
            {"d": document.id},
        )
    ).one()
    [review] = await _review(db, document.id)
    operation = (
        await db.execute(
            text(
                "SELECT generation, fencing_token FROM document_processing_operations WHERE document_id = :d"
            ),
            {"d": document.id},
        )
    ).one()
    payload = (
        artifact.payload if isinstance(artifact.payload, dict) else json.loads(artifact.payload)
    )
    return SimpleNamespace(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document.id,
        revision_id=revision.revision_id,
        review_row_id=review.id,
        review_item_id=review.item_id,
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.artifact_version,
        artifact_hash=artifact.artifact_hash,
        generation=operation.generation,
        fencing_token=operation.fencing_token,
        risks=payload["extracted_risks"],
        saver=saver,
        app=graph.app,
        sessions=independent_sessions,
    )


def _submission(
    w: Any,
    *,
    ordinal: int = 0,
    action: FindingDecisionAction = FindingDecisionAction.CONFIRMED,
    expected: int = 0,
    key: str | None = None,
    reason: str | None = None,
    **overrides: Any,
) -> FindingDecisionSubmission:
    values: dict[str, Any] = {
        "artifact_id": w.artifact_id,
        "artifact_version": w.artifact_version,
        "artifact_hash": w.artifact_hash,
        "document_revision_id": w.revision_id,
        "generation": w.generation,
        "fencing_token": w.fencing_token,
        "source_item_id": risk_source_item_id(w.risks[ordinal]),
        "ordinal": ordinal,
        "action": action,
        "expected_ledger_revision": expected,
        "idempotency_key": key or f"decision-{uuid4().hex}",
        "reason": reason,
    }
    values.update(overrides)
    return FindingDecisionSubmission(**values)


async def _decide(
    w: Any, user: Any, submission: FindingDecisionSubmission, *, tenant_id: UUID | None = None
) -> Any:
    async with w.sessions(tenant_id or w.tenant_id) as session:
        return await RecordFindingDecisionUseCase(session).execute(
            tenant_id=tenant_id or w.tenant_id,
            user=user,
            review_row_id=w.review_row_id,
            submission=submission,
        )


async def _ledger(db: AsyncSession, w: Any) -> list[Any]:
    await db.commit()
    return list(
        (
            await db.execute(
                text(
                    "SELECT ledger_revision, action, reviewer_id, finding_id, reason FROM hitl_finding_decisions "
                    "WHERE review_row_id = :r ORDER BY ledger_revision"
                ),
                {"r": w.review_row_id},
            )
        ).all()
    )


async def _status(db: AsyncSession, w: Any) -> dict[str, Any]:
    await db.commit()
    review = (
        await db.execute(
            text(
                "SELECT current_status::text AS status, review_metadata FROM review_items WHERE id = :r"
            ),
            {"r": w.review_row_id},
        )
    ).one()
    artifacts = (
        await db.execute(
            text(
                "SELECT artifact_version, trust_state, lifecycle_status, artifact_hash FROM document_artifacts "
                "WHERE document_id = :d ORDER BY artifact_version"
            ),
            {"d": w.document_id},
        )
    ).all()
    return {
        "review": review.status,
        "metadata": review.review_metadata or {},
        "artifacts": [tuple(a) for a in artifacts],
    }


# ── individual decisions are provisional ─────────────────────────────────────


async def test_individual_decisions_are_appended_to_the_ledger_and_approve_nothing(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    first = await _decide(
        w, test_user, _submission(w, ordinal=0, action=FindingDecisionAction.CONFIRMED, expected=0)
    )
    second = await _decide(
        w,
        test_user,
        _submission(
            w,
            ordinal=1,
            action=FindingDecisionAction.DISMISSED,
            expected=1,
            reason="not applicable here",
        ),
    )

    assert (first.ledger_revision, first.replayed) == (1, False)
    assert (second.ledger_revision, second.replayed) == (2, False)
    rows = await _ledger(db, w)
    assert [(r.ledger_revision, r.action) for r in rows] == [(1, "CONFIRMED"), (2, "DISMISSED")]
    assert {r.reviewer_id for r in rows} == {str(test_user.id)}, (
        "the reviewer is the authenticated user, never client data"
    )
    assert rows[0].finding_id != rows[1].finding_id

    state = await _status(w=w, db=db)
    assert state["review"] == ReviewStatus.PENDING_REVIEW_REQUIRED.value, (
        "an individual decision never approves"
    )
    assert [(v, t) for v, t, *_ in state["artifacts"]] == [(1, "proposed")], (
        "and never makes the candidate canonical"
    )


async def test_the_final_approval_is_a_separate_act_that_trusts_exactly_the_decided_candidate(
    db: AsyncSession,
    test_user: Any,
    world: Any,
    request_sessions: Any,  # noqa: F811
) -> None:
    w = world
    await _decide(w, test_user, _submission(w, ordinal=0, expected=0))
    await _decide(
        w,
        test_user,
        _submission(
            w, ordinal=1, action=FindingDecisionAction.NEEDS_INFO, expected=1, reason="ask the PM"
        ),
    )
    before = await _status(w=w, db=db)
    assert before["review"] == ReviewStatus.PENDING_REVIEW_REQUIRED.value

    response = await _post_approve(
        request_sessions,
        w.tenant_id,
        w.review_item_id,
        saver=w.saver,
        app=w.app,
        sessions=w.sessions,
        row_id=w.review_row_id,
    )

    assert response.current_status == ReviewStatus.APPROVED
    after = await _status(w=w, db=db)
    assert after["review"] == ReviewStatus.APPROVED.value
    assert [(v, t) for v, t, *_ in after["artifacts"]] == [(1, "trusted")]
    assert after["artifacts"][0][3] == w.artifact_hash, (
        "the artifact that was decided on is the artifact that became trusted"
    )
    assert len(await _ledger(db, w)) == 2, (
        "the approval neither rewrites nor adds finding decisions"
    )

    with pytest.raises(FindingDecisionIdentityError, match="no actionable review"):
        await _decide(
            w,
            test_user,
            _submission(
                w, ordinal=0, action=FindingDecisionAction.DISMISSED, expected=2, reason="too late"
            ),
        )
    assert len(await _ledger(db, w)) == 2


async def test_a_rejection_keeps_the_reason_and_the_decisions_but_never_trusts_the_candidate(
    db: AsyncSession,
    test_user: Any,
    world: Any,
    request_sessions: Any,  # noqa: F811
) -> None:
    w = world
    await _decide(
        w,
        test_user,
        _submission(
            w,
            ordinal=0,
            action=FindingDecisionAction.DISMISSED,
            expected=0,
            reason="duplicated risk",
        ),
    )

    response = await _post_reject(
        request_sessions,
        w.tenant_id,
        w.review_item_id,
        saver=w.saver,
        app=w.app,
        sessions=w.sessions,
        reason="the extraction missed the penalty clause",
        row_id=w.review_row_id,
    )

    assert response.current_status == ReviewStatus.REJECTED
    state = await _status(w=w, db=db)
    assert state["review"] == ReviewStatus.REJECTED.value
    assert not [a for a in state["artifacts"] if a[1] == "trusted"], (
        "a rejected candidate never becomes canonical"
    )
    assert [r.action for r in await _ledger(db, w)] == ["DISMISSED"], (
        "the human history survives the rejection"
    )
    with pytest.raises(FindingDecisionIdentityError):
        await _decide(w, test_user, _submission(w, ordinal=1, expected=1))


# ── a rejection needs a reason (HTTP boundary) ───────────────────────────────


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
async def test_reject_route_refuses_a_missing_or_blank_reason_and_changes_nothing(
    db: AsyncSession, world: Any, authenticated_client: Any, reason: str
) -> None:
    w = world
    before = await _status(w=w, db=db)

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{w.review_item_id}/reject",
        json={"reason": reason, "row_id": str(w.review_row_id)},
    )

    assert response.status_code == 422, response.text
    assert await _status(w=w, db=db) == before


async def test_reject_route_refuses_a_request_without_any_reason_field(
    db: AsyncSession, world: Any, authenticated_client: Any
) -> None:
    w = world
    before = await _status(w=w, db=db)

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{w.review_item_id}/reject", json={"row_id": str(w.review_row_id)}
    )

    assert response.status_code == 422, response.text
    assert await _status(w=w, db=db) == before


@pytest.mark.parametrize("feedback", [None, "", "  "])
async def test_the_resume_route_cannot_be_used_to_reject_without_a_reason(
    db: AsyncSession, world: Any, authenticated_client: Any, feedback: str | None
) -> None:
    w = world
    before = await _status(w=w, db=db)
    body: dict[str, Any] = {"decision": "reject"}
    if feedback is not None:
        body["feedback"] = feedback

    response = await authenticated_client.post(f"/api/v1/hitl/resume/{w.review_row_id}", json=body)

    assert response.status_code == 422, response.text
    assert await _status(w=w, db=db) == before


# ── negatives: contradictory, duplicate, foreign tenant, stale, bypass ──────


async def test_contradictory_decisions_on_the_same_ledger_revision_cannot_both_win(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    await _decide(
        w, test_user, _submission(w, ordinal=0, action=FindingDecisionAction.CONFIRMED, expected=0)
    )

    # A second reviewer who still sees an empty ledger decides the opposite on the same finding.
    with pytest.raises(FindingDecisionRevisionConflict):
        await _decide(
            w,
            test_user,
            _submission(
                w,
                ordinal=0,
                action=FindingDecisionAction.DISMISSED,
                expected=0,
                reason="I disagree",
            ),
        )

    rows = await _ledger(db, w)
    assert [(r.ledger_revision, r.action) for r in rows] == [(1, "CONFIRMED")], (
        "the loser left no trace in the ledger"
    )
    # Changing one's mind is allowed only knowingly: against the revision that was seen, as new history.
    await _decide(
        w,
        test_user,
        _submission(
            w,
            ordinal=0,
            action=FindingDecisionAction.DISMISSED,
            expected=1,
            reason="on reflection, not applicable",
        ),
    )
    assert [(r.ledger_revision, r.action) for r in await _ledger(db, w)] == [
        (1, "CONFIRMED"),
        (2, "DISMISSED"),
    ]


async def test_a_duplicate_decision_is_replayed_not_recorded_twice_and_a_changed_replay_is_refused(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    original = _submission(
        w, ordinal=0, action=FindingDecisionAction.CONFIRMED, expected=0, key="same-request-0001"
    )
    first = await _decide(w, test_user, original)
    again = await _decide(w, test_user, original)

    assert again.replayed is True and again.event_id == first.event_id
    assert len(await _ledger(db, w)) == 1

    changed = _submission(
        w,
        ordinal=0,
        action=FindingDecisionAction.DISMISSED,
        expected=0,
        key="same-request-0001",
        reason="different intent",
    )
    with pytest.raises(FindingDecisionIdempotencyConflict):
        await _decide(w, test_user, changed)
    assert [r.action for r in await _ledger(db, w)] == ["CONFIRMED"]


async def test_approving_twice_commits_the_candidate_once(
    db: AsyncSession,
    world: Any,
    request_sessions: Any,  # noqa: F811
) -> None:
    w = world
    first = await _post_approve(
        request_sessions,
        w.tenant_id,
        w.review_item_id,
        saver=w.saver,
        app=w.app,
        sessions=w.sessions,
        row_id=w.review_row_id,
    )
    second = await _post_approve(
        request_sessions,
        w.tenant_id,
        w.review_item_id,
        saver=w.saver,
        app=w.app,
        sessions=w.sessions,
        row_id=w.review_row_id,
    )

    assert first.current_status == second.current_status == ReviewStatus.APPROVED
    state = await _status(w=w, db=db)
    assert [(v, t) for v, t, *_ in state["artifacts"]] == [(1, "trusted")], (
        "one commit, no second version"
    )


async def test_a_contradictory_final_decision_after_the_first_is_refused(
    db: AsyncSession,
    world: Any,
    request_sessions: Any,  # noqa: F811
) -> None:
    w = world
    await _post_approve(
        request_sessions,
        w.tenant_id,
        w.review_item_id,
        saver=w.saver,
        app=w.app,
        sessions=w.sessions,
        row_id=w.review_row_id,
    )

    with pytest.raises(HTTPException) as refused:
        await _post_reject(
            request_sessions,
            w.tenant_id,
            w.review_item_id,
            saver=w.saver,
            app=w.app,
            sessions=w.sessions,
            reason="changed my mind",
            row_id=w.review_row_id,
        )

    assert refused.value.status_code == 400
    assert "already approved" in str(refused.value.detail)
    state = await _status(w=w, db=db)
    assert state["review"] == ReviewStatus.APPROVED.value
    assert [(v, t) for v, t, *_ in state["artifacts"]] == [(1, "trusted")]


async def test_another_tenant_can_neither_record_nor_approve(
    db: AsyncSession,
    test_user: Any,
    test_user_2: Any,
    world: Any,
    request_sessions: Any,  # noqa: F811
) -> None:
    w = world
    before = await _status(w=w, db=db)
    stranger = test_user_2

    # A user of tenant B naming tenant A is not a reviewer of tenant A.
    with pytest.raises(FindingReviewerNotAuthorized):
        await _decide(w, stranger, _submission(w, ordinal=0), tenant_id=w.tenant_id)
    # A user of tenant B acting inside tenant B cannot see tenant A's review at all.
    with pytest.raises(FindingDecisionIdentityError, match="no actionable review"):
        await _decide(w, stranger, _submission(w, ordinal=0), tenant_id=stranger.tenant_id)
    # And the approval route, scoped to tenant B, does not find tenant A's item.
    with pytest.raises(HTTPException) as refused:
        await _post_approve(
            request_sessions,
            stranger.tenant_id,
            w.review_item_id,
            saver=w.saver,
            app=w.app,
            sessions=w.sessions,
            row_id=w.review_row_id,
        )
    assert refused.value.status_code in {400, 404}

    assert await _ledger(db, w) == []
    assert await _status(w=w, db=db) == before


async def test_a_decision_pinned_to_a_stale_candidate_or_authority_is_refused(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    stale_variants = {
        "another artifact hash": {"artifact_hash": "0" * 64},
        "an older artifact version": {"artifact_version": w.artifact_version + 1},
        "a superseded generation": {"generation": w.generation + 1},
        "a superseded fencing token": {"fencing_token": w.fencing_token + 1},
    }
    for name, override in stale_variants.items():
        with pytest.raises(FindingDecisionIdentityError):
            await _decide(w, test_user, _submission(w, ordinal=0, **override))
        assert await _ledger(db, w) == [], f"{name} must leave no decision behind"

    # The authority moves on (takeover / reprocess): a decision built for the old one fails closed.
    await db.execute(
        text(
            "UPDATE document_processing_operations SET fencing_token = fencing_token + 1 WHERE document_id = :d"
        ),
        {"d": w.document_id},
    )
    await db.commit()
    with pytest.raises(FindingDecisionIdentityError):
        await _decide(w, test_user, _submission(w, ordinal=0))
    assert await _ledger(db, w) == []


async def test_nothing_reaches_a_final_state_without_the_review_route(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    before = await _status(w=w, db=db)

    viewer = SimpleNamespace(
        id=uuid4(), tenant_id=w.tenant_id, is_active=True, role=UserRole.VIEWER
    )
    api_client = SimpleNamespace(
        id=uuid4(), tenant_id=w.tenant_id, is_active=True, role=UserRole.API
    )
    for non_human in (viewer, api_client):
        with pytest.raises(FindingReviewerNotAuthorized):
            await _decide(w, non_human, _submission(w, ordinal=0))

    # A finding that is not in the exact candidate cannot be decided on.
    with pytest.raises(FindingDecisionIdentityError, match="not a member|exact candidate|member"):
        await _decide(
            w, test_user, _submission(w, ordinal=0, source_item_id="risk-sha256:" + "f" * 64)
        )
    with pytest.raises(FindingDecisionIdentityError):
        await _decide(
            w,
            test_user,
            _submission(
                w, ordinal=0, **{"source_item_id": risk_source_item_id(w.risks[0])}
            ).model_copy(update={"ordinal": len(w.risks)}),
        )

    # A correction needs its reason and replacement text before it is even a valid submission.
    with pytest.raises(ValueError):
        _submission(w, ordinal=0, action=FindingDecisionAction.CORRECTION_PROPOSED)

    assert await _ledger(db, w) == []
    assert await _status(w=w, db=db) == before, "none of it approved, rejected or trusted anything"


async def test_the_ledger_rejects_direct_sql_that_the_application_would_refuse_and_is_append_only(
    db: AsyncSession, test_user: Any, world: Any
) -> None:
    w = world
    await _decide(w, test_user, _submission(w, ordinal=0, expected=0))
    [event] = await _ledger(db, w)

    base = {
        "tenant_id": w.tenant_id,
        "project_id": w.project_id,
        "review_row_id": w.review_row_id,
        "document_id": w.document_id,
        "revision": w.revision_id,
        "artifact_id": w.artifact_id,
        "version": w.artifact_version,
        "hash": w.artifact_hash,
        "generation": w.generation,
        "fencing": w.fencing_token,
        "reviewer": str(test_user.id),
        "finding": event.finding_id,
    }
    insert = text(
        "INSERT INTO hitl_finding_decisions (event_id, tenant_id, project_id, review_row_id, document_id, "
        "document_revision_id, artifact_id, artifact_version, artifact_hash, generation, fencing_token, "
        "thread_id, checkpoint_id, finding_id, source_item_id, source_ordinal, finding_kind, action, "
        "reviewer_id, created_by, expected_ledger_revision, ledger_revision, idempotency_key) "
        "SELECT gen_random_uuid(), :tenant_id, :project_id, :review_row_id, :document_id, :revision, "
        ":artifact_id, :version, :hash, :generation, :fencing, r.thread_id, r.checkpoint_id, :finding, "
        "'risk-sha256:x', 0, 'RISK', 'CONFIRMED', :reviewer, :reviewer, :expected, :expected + 1, :key "
        "FROM review_items r WHERE r.id = :review_row_id"
    )
    with pytest.raises(
        DBAPIError
    ):  # stale expected revision: another reviewer already appended revision 1
        await db.execute(insert, {**base, "expected": 0, "key": "direct-sql-stale-0001"})
    await db.rollback()
    with pytest.raises(
        DBAPIError
    ):  # a fabricated authority: the guard re-reads the live fencing token
        await db.execute(
            insert,
            {**base, "fencing": w.fencing_token + 7, "expected": 1, "key": "direct-sql-fenced-01"},
        )
    await db.rollback()
    with pytest.raises(DBAPIError):  # the history cannot be rewritten ...
        await db.execute(
            text("UPDATE hitl_finding_decisions SET action = 'DISMISSED', reason = 'tampered'")
        )
    await db.rollback()
    with pytest.raises(DBAPIError):  # ... or erased
        await db.execute(text("DELETE FROM hitl_finding_decisions"))
    await db.rollback()

    assert [(r.ledger_revision, r.action) for r in await _ledger(db, w)] == [(1, "CONFIRMED")]
