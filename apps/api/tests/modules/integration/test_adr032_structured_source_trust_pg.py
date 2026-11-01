"""ADR-032 against real PostgreSQL: explicit human trust for a Budget/Schedule XLSX source.

Proves, in real transactions: the candidate is PROPOSED only on request; approval promotes the
exact bound candidate through the typed ``commit_structured_candidate`` without any projection,
analytic-materialization, ProjectGraph, Coherence or alert effect; stale/tampered/foreign inputs
fail closed (409/422/404); the legacy decision route refuses a bound, thread-less review; and the
S7 link services are unchanged (409 before approval, 201/CURRENT after, STALE_SOURCE after a
re-upload).
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import openpyxl
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.canonical_structured_wbs_links import (
    APPROVAL,
    ApproveStructuredWBSLinkService,
    ImmutableXLSXRowReader,
    ReadStructuredWBSLinksService,
    StructuredWBSLinkError,
)
from src.analysis.application.structured_source_trust import (
    DecideStructuredSourceTrustService,
    ImmutableStructuredSourceVerifier,
    RequestStructuredSourceTrustService,
    StructuredTrustConflict,
    StructuredTrustForbidden,
    StructuredTrustInvalid,
    StructuredTrustNotFound,
)
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import (
    BoundReviewRequiresTrustDecision,
    CandidateBinding,
    TrustState,
    WrongTrustOperationError,
    ensure_legacy_decision_allowed,
)
from src.core.auth.models import Tenant, User, UserRole
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.human_in_the_loop_service import HumanInTheLoopService
from src.modules.hitl.domain.entities import ReviewStatus
from src.temporal.adapters.persistence.current_revision_resolver import (
    SqlAlchemyCurrentRevisionResolver,
)
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.temporal.domain.current_revision import CurrentRevisionStatus
from tests.integration.analysis.test_s7_review_service_settlement_pg import (
    _world as _technical_world,
)

pytestmark = pytest.mark.asyncio

KEY = "adr032-key-"


class _Storage:
    download_object_is_temporary = False

    def __init__(self) -> None:
        self.mapping: dict[str, Path] = {}

    async def download_object(self, key: str) -> Path:
        return self.mapping[key]


async def _world(db: AsyncSession, tmp_path: Path) -> dict:
    """The shared S7 world minus its synthetic technical artifact (irrelevant here, and its
    stub payload is not a valid DocumentArtifact for the canonical readers)."""
    w = await _technical_world(db, tmp_path)
    await db.execute(text("DELETE FROM document_artifacts WHERE document_id = cast(:d as uuid)"), {"d": str(w["document"])})
    await db.commit()
    return w


async def _approver(db: AsyncSession, w: dict) -> UUID:
    """A SECOND human of the same tenant (the requester is ``w['actor']``)."""
    other = await db.scalar(
        select(User).where(
            User.tenant_id == w["tenant"], User.id != w["actor"], User.role == UserRole.ADMIN
        )
    )
    assert other is not None
    other.clerk_user_id = f"clerk-adr032-{other.id.hex}"
    await db.commit()
    return other.id


def _workbook(path: Path, family: str, node: UUID, extra: str = "") -> str:
    book = openpyxl.Workbook()
    sheet = book.active
    if family == "budget":
        sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency", "Tax Basis", "WBS Node ID"])
        sheet.append([f"Concrete foundation{extra}", 2, "m3", 120, 240, "EUR", "NET", str(node)])
    else:
        sheet.append(["Task", "Start Date", "End Date", "Duration", "Activity ID", "WBS Node ID"])
        sheet.append([f"Foundations{extra}", "2026-11-01", "2026-11-02", 2, "ACT-100", str(node)])
    book.save(path)
    book.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _document(
    db: AsyncSession, w: dict, tmp_path: Path, storage: _Storage, family: str = "budget"
) -> dict:
    path = tmp_path / f"{family}-{uuid4().hex[:6]}.xlsx"
    digest = _workbook(path, family, w["node"])
    document_id, revision_id = uuid4(), uuid4()
    key = f"synthetic/adr032/{revision_id}.xlsx"
    storage.mapping[key] = path
    db.add(
        DocumentORM(
            id=document_id, tenant_id=w["tenant"], project_id=w["project"],
            document_type=DocumentType.BUDGET if family == "budget" else DocumentType.SCHEDULE,
            filename=f"{family}.xlsx", file_format=".xlsx", file_hash=digest, created_by=w["actor"],
        )
    )
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        DocumentRevisionORM(
            revision_id=revision_id, tenant_id=w["tenant"], project_id=w["project"],
            document_id=document_id, rev_no=1, blob_hash=digest, blob_key=key,
            valid_from=now, created_at=now,
        )
    )
    await db.commit()
    return {"family": family, "document": document_id, "revision": revision_id, "digest": digest, "path": path}


async def _reupload(db: AsyncSession, w: dict, tmp_path: Path, storage: _Storage, doc: dict) -> UUID:
    """A second immutable revision of the same document (a re-upload)."""
    path = tmp_path / f"reupload-{uuid4().hex[:6]}.xlsx"
    digest = _workbook(path, doc["family"], w["node"], extra=" v2")
    revision_id = uuid4()
    key = f"synthetic/adr032/{revision_id}.xlsx"
    storage.mapping[key] = path
    now = datetime.now(UTC).replace(tzinfo=None)
    await db.execute(
        update(DocumentRevisionORM)
        .where(DocumentRevisionORM.revision_id == doc["revision"])
        .values(valid_to=now)
    )
    db.add(
        DocumentRevisionORM(
            revision_id=revision_id, tenant_id=w["tenant"], project_id=w["project"],
            document_id=doc["document"], rev_no=2, parent_revision_id=doc["revision"],
            blob_hash=digest, blob_key=key, valid_from=now, created_at=now,
        )
    )
    await db.commit()
    return revision_id


def _verifier(storage: _Storage) -> ImmutableStructuredSourceVerifier:
    return ImmutableStructuredSourceVerifier(storage, ExcelFileParser())  # type: ignore[arg-type]


async def _request(factory, storage, w, doc, *, actor=None, revision=None, key=f"{KEY}req", tenant=None):
    async with factory() as session:
        receipt = await RequestStructuredSourceTrustService(session, _verifier(storage)).execute(
            tenant_id=tenant or w["tenant"], document_id=doc["document"],
            revision_id=revision or doc["revision"], actor_user_id=actor or w["actor"],
            idempotency_key=key, reason="Please consider this source",
        )
        await session.commit()
    return receipt


async def _decide(factory, storage, w, receipt, decision, *, actor, key=f"{KEY}dec", tenant=None, **over):
    args = {
        "tenant_id": tenant or w["tenant"], "review_row_id": receipt.review_row_id,
        "artifact_id": receipt.artifact_id, "artifact_version": receipt.artifact_version,
        "artifact_hash": receipt.artifact_hash, "decision": decision, "actor_user_id": actor,
        "idempotency_key": key, "reason": "Human decision on the exact source",
    }
    args.update(over)
    async with factory() as session:
        out = await DecideStructuredSourceTrustService(session, _verifier(storage)).execute(**args)
        await session.commit()
    return out


async def _count(factory, sql: str, **params) -> int:
    async with factory() as session:
        return int(await session.scalar(text(sql), params) or 0)


async def _effects(factory, w) -> dict[str, int]:
    p = {"p": str(w["project"])}
    return {
        "analyses": await _count(factory, "SELECT count(*) FROM analyses WHERE project_id = cast(:p as uuid)", **p),
        "alerts": await _count(factory, "SELECT count(*) FROM alerts WHERE project_id = cast(:p as uuid)", **p),
        "obligations": await _count(
            factory,
            "SELECT count(*) FROM system_recovery.trusted_projection_index WHERE project_id = cast(:p as uuid)",
            **p,
        ),
        "graph_events": await _count(
            factory,
            "SELECT count(*) FROM project_events WHERE project_id = cast(:p as uuid) AND event_type IN "
            "('analysis.persisted','graph.completed','materialization.completed','revision.analyzed')",
            **p,
        ),
    }


async def _resolve(factory, w, doc):
    async with factory() as session:
        return await SqlAlchemyCurrentRevisionResolver(session).resolve(
            tenant_id=w["tenant"], document_id=doc["document"]
        )


async def _artifact(factory, artifact_id: UUID) -> DocumentArtifactORM:
    async with factory() as session:
        row = await session.scalar(select(DocumentArtifactORM).where(DocumentArtifactORM.artifact_id == artifact_id))
        assert row is not None
        return row


async def _review(factory, tenant: UUID, row_id: UUID):
    async with factory() as session:
        review = await SqlAlchemyReviewQueueRepository(session, tenant).get_review_item_by_row_id(row_id)
        assert review is not None
        return review


# 1 ------------------------------------------------------------------------------------------
async def test_request_creates_one_proposed_candidate_and_bound_review_without_side_effects(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    before = await _effects(test_session_factory, w)

    receipt = await _request(test_session_factory, storage, w, doc)

    assert not receipt.replayed and receipt.trust_state == "proposed" and receipt.row_count == 1
    row = await _artifact(test_session_factory, receipt.artifact_id)
    assert row.trust_state == "proposed" and row.document_revision_id == doc["revision"]
    source = row.payload["structured_source"]
    assert source["family"] == "budget" and source["blob_sha256"] == doc["digest"]
    assert source["row_count"] == 1 and len(source["content_digest"]) == 64
    assert row.payload["extracted_risks"] == [] and row.payload["bom_items"] == []
    review = await _review(test_session_factory, w["tenant"], receipt.review_row_id)
    assert review.current_status is ReviewStatus.PENDING_REVIEW_REQUIRED
    assert review.metadata["trust_kind"] == "structured_source" and "thread_id" not in review.metadata
    assert CandidateBinding.from_json(review.metadata["candidate_binding"]).artifact_hash == receipt.artifact_hash
    assert await _effects(test_session_factory, w) == before
    async with test_session_factory() as session:
        repo = SqlAlchemyDocumentArtifactRepository(session)
        assert await repo.list_pending_candidates(project_id=w["project"], tenant_id=w["tenant"]) == []
        assert await repo.list_trusted_for_project(project_id=w["project"], tenant_id=w["tenant"]) == []
        requested = await session.scalar(
            select(ProjectEventORM).where(ProjectEventORM.event_type == "structured_source.trust_requested")
        )
        assert requested is not None and requested.payload["requested_by"] == str(w["actor"])
    assert (await _resolve(test_session_factory, w, doc)).status is not CurrentRevisionStatus.TRUSTED


# 2 ------------------------------------------------------------------------------------------
async def test_request_is_idempotent(db: AsyncSession, test_session_factory, tmp_path: Path) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    first = await _request(test_session_factory, storage, w, doc)
    second = await _request(test_session_factory, storage, w, doc, key=f"{KEY}other-key")
    assert second.replayed and second.artifact_id == first.artifact_id
    assert second.review_row_id == first.review_row_id
    assert await _count(test_session_factory, "SELECT count(*) FROM document_artifacts WHERE document_id = cast(:d as uuid)", d=str(doc["document"])) == 1
    assert await _count(test_session_factory, "SELECT count(*) FROM review_items WHERE document_id = cast(:d as uuid)", d=str(doc["document"])) == 1


# 3 ------------------------------------------------------------------------------------------
async def test_tampered_bytes_are_refused_at_request_and_at_approval(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    tampered = await _document(db, w, tmp_path, storage)
    tampered["path"].write_bytes(tampered["path"].read_bytes() + b"tampered")
    with pytest.raises(StructuredTrustInvalid):
        await _request(test_session_factory, storage, w, tampered)
    assert await _count(test_session_factory, "SELECT count(*) FROM document_artifacts WHERE document_id = cast(:d as uuid)", d=str(tampered["document"])) == 0

    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    doc["path"].write_bytes(doc["path"].read_bytes() + b"tampered-after-proposal")
    with pytest.raises(StructuredTrustInvalid):
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"


# 4 + 10 -------------------------------------------------------------------------------------
async def test_approve_trusts_exact_candidate_with_no_projection_or_materialization_effects(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    before = await _effects(test_session_factory, w)

    out = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)

    assert out.trust_state == "trusted" and out.review_status == "APPROVED" and not out.self_approved
    row = await _artifact(test_session_factory, receipt.artifact_id)
    assert row.trust_state == "trusted" and row.lifecycle_status == "active"
    review = await _review(test_session_factory, w["tenant"], receipt.review_row_id)
    assert review.current_status is ReviewStatus.APPROVED
    resolved = await _resolve(test_session_factory, w, doc)
    assert resolved.status is CurrentRevisionStatus.TRUSTED and resolved.revision_id == doc["revision"]
    # E1-E9: no projection obligation, no analysis row, no alert, no graph/materialization event.
    assert await _effects(test_session_factory, w) == before
    async with test_session_factory() as session:
        repo = SqlAlchemyDocumentArtifactRepository(session)
        assert await repo.list_trusted_for_project(project_id=w["project"], tenant_id=w["tenant"]) == []
        assert await repo.list_active_for_project(project_id=w["project"], tenant_id=w["tenant"]) == []
        assert await repo.list_pending_candidates(project_id=w["project"], tenant_id=w["tenant"]) == []
        decided = await session.scalar(
            select(ProjectEventORM).where(ProjectEventORM.event_type == "structured_source.trust_decided")
        )
        assert decided is not None
        assert decided.payload["self_approved"] is False and decided.payload["decision"] == "APPROVE"
        assert decided.payload["source_assessment"] == "NOT_ASSESSED"
        assert decided.actor == f"user:{approver}"
    # Exact replay is idempotent; a conflicting second decision is refused.
    replay = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert replay.replayed and replay.event_id == out.event_id
    with pytest.raises(StructuredTrustConflict):
        await _decide(test_session_factory, storage, w, receipt, "REJECT", actor=approver, key=f"{KEY}dec2")


# 5 ------------------------------------------------------------------------------------------
async def test_reject_records_rejection_and_keeps_source_unresolved(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    out = await _decide(test_session_factory, storage, w, receipt, "REJECT", actor=approver)
    assert out.trust_state == "rejected" and out.review_status == "REJECTED"
    row = await _artifact(test_session_factory, receipt.artifact_id)
    assert row.trust_state == "rejected" and row.lifecycle_status == "superseded"
    assert (await _resolve(test_session_factory, w, doc)).status is not CurrentRevisionStatus.TRUSTED
    # A rejected source can be proposed again (a NEW explicit human request, a new version).
    again = await _request(test_session_factory, storage, w, doc, key=f"{KEY}again")
    assert not again.replayed and again.artifact_version == receipt.artifact_version + 1


# 6 ------------------------------------------------------------------------------------------
async def test_stale_binding_and_superseded_candidate_fail_closed(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    for override in ({"artifact_hash": "0" * 64}, {"artifact_version": 99}, {"artifact_id": uuid4()}):
        with pytest.raises(StructuredTrustConflict):
            await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver, **override)
    # A re-upload + new request supersedes the first candidate and closes its review.
    new_revision = await _reupload(db, w, tmp_path, storage, doc)
    with pytest.raises(StructuredTrustConflict):  # the first revision is no longer current
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    fresh = await _request(test_session_factory, storage, w, doc, revision=new_revision, key=f"{KEY}rev2")
    old = await _artifact(test_session_factory, receipt.artifact_id)
    assert old.trust_state == "superseded"
    assert (await _review(test_session_factory, w["tenant"], receipt.review_row_id)).current_status is ReviewStatus.CLOSED
    with pytest.raises(StructuredTrustConflict):
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert fresh.artifact_version == receipt.artifact_version + 1
    with pytest.raises(StructuredTrustConflict):  # only the current revision can be proposed
        await _request(test_session_factory, storage, w, doc, revision=doc["revision"], key=f"{KEY}old")


# 7 ------------------------------------------------------------------------------------------
async def test_concurrent_opposite_decisions_have_exactly_one_winner(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    results = await asyncio.gather(
        _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver, key=f"{KEY}a"),
        _decide(test_session_factory, storage, w, receipt, "REJECT", actor=approver, key=f"{KEY}b"),
        return_exceptions=True,
    )
    winners = [r for r in results if not isinstance(r, BaseException)]
    losers = [r for r in results if isinstance(r, BaseException)]
    assert len(winners) == 1 and len(losers) == 1 and isinstance(losers[0], StructuredTrustConflict)
    state = (await _artifact(test_session_factory, receipt.artifact_id)).trust_state
    assert state == ("trusted" if winners[0].decision == "APPROVE" else "rejected")
    assert await _count(
        test_session_factory,
        "SELECT count(*) FROM project_events WHERE event_type = 'structured_source.trust_decided' AND project_id = cast(:p as uuid)",
        p=str(w["project"]),
    ) == 1


# 8 ------------------------------------------------------------------------------------------
async def test_tenant_isolation(db: AsyncSession, test_session_factory, tmp_path: Path) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    with pytest.raises(StructuredTrustNotFound):
        await _request(test_session_factory, storage, w, doc, tenant=uuid4())
    receipt = await _request(test_session_factory, storage, w, doc)
    with pytest.raises(StructuredTrustNotFound):
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=w["actor"], tenant=uuid4())
    with pytest.raises(StructuredTrustForbidden):  # a user of no tenant is not a human approver
        await _request(test_session_factory, storage, w, doc, actor=uuid4())
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"


# 9 ------------------------------------------------------------------------------------------
async def test_legacy_decision_route_is_refused_for_bound_threadless_reviews_only(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)

    class _Silent:
        async def send_escalation_alert(self, *_a, **_k) -> None: ...

    async with test_session_factory() as session:
        repo = SqlAlchemyReviewQueueRepository(session, w["tenant"])
        service = HumanInTheLoopService(repo, _Silent(), None)  # type: ignore[arg-type]
        with pytest.raises(BoundReviewRequiresTrustDecision, match="structured-source-trust/decisions"):
            await service.approve_item(receipt.review_row_id, w["actor"], "Reviewer")
        await session.rollback()
    review = await _review(test_session_factory, w["tenant"], receipt.review_row_id)
    assert review.current_status is ReviewStatus.PENDING_REVIEW_REQUIRED
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"
    # The pure guard: graph reviews (thread) and unbound legacy reviews are unaffected.
    ensure_legacy_decision_allowed({"candidate_binding": {"artifact_id": "x"}, "thread_id": "t-1"})
    ensure_legacy_decision_allowed({"review_type": "legacy"})
    ensure_legacy_decision_allowed(None)
    with pytest.raises(BoundReviewRequiresTrustDecision):
        ensure_legacy_decision_allowed({"candidate_binding": {"artifact_id": "x"}})
    with pytest.raises(BoundReviewRequiresTrustDecision):
        ensure_legacy_decision_allowed({"trust_candidate_required": True})


async def _flags(factory, doc: dict) -> dict:
    """The exact SQL rule every canonical reader embeds (resolved / trusted / canonical)."""
    from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral

    sql = (
        "SELECT cur.resolved, cur.trusted, cur.canonical, cur.revision_id "
        "FROM public.documents d CROSS JOIN LATERAL "
        + current_revision_lateral("d.id", "d.tenant_id")
        + " AS cur WHERE d.id = cast(:d as uuid)"
    )
    async with factory() as session:
        row = (await session.execute(text(sql), {"d": str(doc["document"])})).one()
    return {"resolved": row.resolved, "trusted": row.trusted, "canonical": row.canonical}


# E5 -----------------------------------------------------------------------------------------
async def test_unevaluated_pending_trusted_and_rejected_sources_stay_distinguishable(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    """An unrequested source, a pending candidate, a trusted source and a rejected source are four
    different canonical states; none is reported as another (conditions 1 and 3 of the ADR)."""
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    assert await _flags(test_session_factory, doc) == {"resolved": True, "trusted": False, "canonical": True}
    receipt = await _request(test_session_factory, storage, w, doc)
    # Pending: still the resolved revision, but NOT canonical input -- the budget evaluation reports
    # "not evaluated" and its alerts are preserved (a pending proposal never moves canonical alerts).
    assert await _flags(test_session_factory, doc) == {"resolved": True, "trusted": False, "canonical": False}
    await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert await _flags(test_session_factory, doc) == {"resolved": True, "trusted": True, "canonical": True}
    rejected = await _document(db, w, tmp_path, storage, family="schedule")
    other = await _request(test_session_factory, storage, w, rejected, key=f"{KEY}r2")
    await _decide(test_session_factory, storage, w, other, "REJECT", actor=approver, key=f"{KEY}rj2")
    # Rejected: not resolved at all (fail closed) -- distinct from "never requested".
    assert await _flags(test_session_factory, rejected) == {"resolved": False, "trusted": False, "canonical": False}
    # The structured candidate never reaches Health/Coherence inputs, whatever its state.
    async with test_session_factory() as session:
        repo = SqlAlchemyDocumentArtifactRepository(session)
        assert await repo.list_trusted_for_project(project_id=w["project"], tenant_id=w["tenant"]) == []
        assert await repo.list_pending_candidates(project_id=w["project"], tenant_id=w["tenant"]) == []


# 11 -----------------------------------------------------------------------------------------
async def test_reupload_after_trust_does_not_inherit_trust(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert (await _resolve(test_session_factory, w, doc)).status is CurrentRevisionStatus.TRUSTED
    new_revision = await _reupload(db, w, tmp_path, storage, doc)
    after = await _resolve(test_session_factory, w, doc)
    assert not (after.status is CurrentRevisionStatus.TRUSTED and after.revision_id == new_revision)
    fresh = await _request(test_session_factory, storage, w, doc, revision=new_revision, key=f"{KEY}rev2")
    assert (await _artifact(test_session_factory, fresh.artifact_id)).trust_state == "proposed"
    still = await _resolve(test_session_factory, w, doc)
    assert not (still.status is CurrentRevisionStatus.TRUSTED and still.revision_id == new_revision)


# 12 -----------------------------------------------------------------------------------------
async def test_s7_link_is_409_before_approval_current_after_and_stale_once_new_revision_is_trusted(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    reader = ImmutableXLSXRowReader(storage, ExcelFileParser())  # type: ignore[arg-type]

    def args() -> dict:
        return {
            "tenant_id": w["tenant"], "project_id": w["project"], "actor_user_id": w["actor"],
            "family": "budget", "source_document_id": doc["document"], "source_revision_id": doc["revision"],
            "expected_blob_hash": doc["digest"], "source_locator": "Sheet!2",
            "expected_wbs_baseline_id": w["baseline"], "expected_wbs_node_id": w["node"],
            "approval": APPROVAL, "idempotency_key": f"{KEY}link", "reason": "Human links the exact row",
        }

    async with test_session_factory() as session:  # untrusted source: the S7 409 stays
        with pytest.raises(StructuredWBSLinkError):
            await ApproveStructuredWBSLinkService(session, reader).execute(**args())
        await session.rollback()
    receipt = await _request(test_session_factory, storage, w, doc)
    async with test_session_factory() as session:  # still only PROPOSED
        with pytest.raises(StructuredWBSLinkError):
            await ApproveStructuredWBSLinkService(session, reader).execute(**args())
        await session.rollback()
    await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    async with test_session_factory() as session:
        link = await ApproveStructuredWBSLinkService(session, reader).execute(**args())
        assert not link.replayed
        await session.commit()
    async with test_session_factory() as session:
        states = [e.state for e in await ReadStructuredWBSLinksService(session, reader).list(
            tenant_id=w["tenant"], project_id=w["project"])]
    assert states == ["CURRENT"]
    # A re-upload alone does not move canonical state: the last TRUSTED revision still speaks
    # for the document (S7 link services are unmodified), so the link stays CURRENT against it.
    new_revision = await _reupload(db, w, tmp_path, storage, doc)
    async with test_session_factory() as session:
        states = [e.state for e in await ReadStructuredWBSLinksService(session, reader).list(
            tenant_id=w["tenant"], project_id=w["project"])]
    assert states == ["CURRENT"]
    # Once the NEW revision is explicitly trusted, the link to the old revision is STALE_SOURCE.
    fresh = await _request(test_session_factory, storage, w, doc, revision=new_revision, key=f"{KEY}rev2")
    await _decide(test_session_factory, storage, w, fresh, "APPROVE", actor=approver, key=f"{KEY}dec2")
    async with test_session_factory() as session:
        states = [e.state for e in await ReadStructuredWBSLinksService(session, reader).list(
            tenant_id=w["tenant"], project_id=w["project"])]
    assert states == ["STALE_SOURCE"]


# 13 -----------------------------------------------------------------------------------------
async def test_self_approval_needs_an_audited_tenant_exception(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    with pytest.raises(StructuredTrustForbidden, match="separation of duties"):
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=w["actor"])
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"
    # Rejecting your own request grants no trust and needs no exception.
    other = await _document(db, w, tmp_path, storage, family="schedule")
    to_reject = await _request(test_session_factory, storage, w, other, key=f"{KEY}rej")
    rejected = await _decide(test_session_factory, storage, w, to_reject, "REJECT", actor=w["actor"], key=f"{KEY}rj")
    assert rejected.trust_state == "rejected" and rejected.self_approved
    # The explicit, audited tenant exception.
    await db.execute(
        update(Tenant).where(Tenant.id == w["tenant"]).values(
            settings={"trust_governance": {"structured_source_self_approval": True}}
        )
    )
    await db.commit()
    out = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=w["actor"], key=f"{KEY}self")
    assert out.self_approved and out.trust_state == "trusted"
    async with test_session_factory() as session:
        event = await session.scalar(
            select(ProjectEventORM).where(
                ProjectEventORM.event_type == "structured_source.trust_decided",
                ProjectEventORM.payload["decision"].astext == "APPROVE",
            )
        )
        assert event is not None and event.payload["self_approved"] is True
        assert event.payload["separation_of_duties"] == "SELF_APPROVAL_TENANT_EXCEPTION"


# Authority separation -----------------------------------------------------------------------
async def test_the_two_trust_operations_never_cross(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    binding = CandidateBinding(receipt.artifact_id, doc["document"], receipt.artifact_version, receipt.artifact_hash)
    async with test_session_factory() as session:
        repo = SqlAlchemyDocumentArtifactRepository(session)
        with pytest.raises(WrongTrustOperationError):
            await repo.commit_candidate(binding, tenant_id=w["tenant"])
        with pytest.raises(WrongTrustOperationError):
            await repo.reject_candidate(binding, tenant_id=w["tenant"])
        await session.rollback()
    # An ANALYSIS candidate cannot be promoted by the structured command.
    other_doc = await _document(db, w, tmp_path, storage, family="schedule")
    async with test_session_factory() as session:
        repo = SqlAlchemyDocumentArtifactRepository(session)
        await repo.save(
            DocumentArtifact(document_id=str(other_doc["document"]), doc_type="schedule"),
            project_id=w["project"], tenant_id=w["tenant"], trust_state=TrustState.PROPOSED,
        )
        await session.commit()
        analysis = await session.scalar(
            select(DocumentArtifactORM).where(DocumentArtifactORM.document_id == other_doc["document"])
        )
        assert analysis is not None and "structured_source" not in analysis.payload
        analysis_binding = CandidateBinding(
            analysis.artifact_id, analysis.document_id, int(analysis.artifact_version), str(analysis.artifact_hash)
        )
        with pytest.raises(WrongTrustOperationError):
            await repo.commit_structured_candidate(analysis_binding, tenant_id=w["tenant"])
        await session.rollback()
    # A pending analysis candidate of the document is never superseded by a structured request.
    with pytest.raises(StructuredTrustConflict) as pending:
        await _request(test_session_factory, storage, w, other_doc, key=f"{KEY}blocked")
    assert pending.value.code == "analysis_candidate_pending"
    assert await _count(
        test_session_factory,
        "SELECT count(*) FROM document_artifacts WHERE document_id = cast(:d as uuid) AND trust_state = 'proposed'",
        d=str(other_doc["document"]),
    ) == 1
