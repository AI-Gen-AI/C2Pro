"""ACC-01 S7: real PostgreSQL service settlement, not a mocked audit assertion.

Creates a governed, human-approved WBS through existing product-service fixtures,
a revision-pinned synthetic DOCX, and a Clerk-linked human reviewer. The service
must persist only an audit event; no canonical technical/WBS link or score.
This is NOT a Clerk-browser E2E or production qualification.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import docx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.record_technical_wbs_review import (
    ImmutableDocxTechnicalTextReader,
    RecordTechnicalWBSReviewService,
    TechnicalMappingDecision,
    TechnicalMappingReviewError,
)
from src.core.auth.models import User
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.wbs.adapters.persistence.governance_models import WBSBaselineORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _baseline_one

pytestmark = pytest.mark.asyncio

SOURCE = "Section 4.1.2 Concrete shall exceed 35 MPa."
EVENT_TYPE = "technical.wbs_link_reviewed"


class _ImmutableLocalStorage:
    """Only this isolated, SHA-verified synthetic file is readable."""

    download_object_is_temporary = False

    def __init__(self, path: Path, key: str) -> None:
        self.path = path
        self.key = key

    async def download_object(self, key: str) -> Path:
        assert key == self.key
        return self.path


async def _world(
    db: AsyncSession,
    tmp_path: Path,
    document_type: DocumentType = DocumentType.TECHNICAL_SPEC,
):
    scope = await _scope(db)
    _, ids, applied = await _baseline_one(db, scope)
    baseline = applied.baseline_id
    node = ids["1.1"]

    # Production Clerk bootstrap can have is_verified=False; the authenticated
    # principal is verified at the HTTP boundary and linked by clerk_user_id.
    actor = await db.get(User, scope.author.user_id)
    assert actor is not None
    actor.clerk_user_id = f"clerk-s7-pg-{actor.id.hex}"
    actor.is_verified = False
    await db.commit()

    file = tmp_path / "technical-s7.docx"
    source = docx.Document()
    source.add_paragraph(SOURCE)
    source.save(file)
    digest = hashlib.sha256(file.read_bytes()).hexdigest()

    document, revision, clause = uuid4(), uuid4(), uuid4()
    key = f"synthetic/s7/{revision}.docx"
    db.add(
        DocumentORM(
            id=document,
            tenant_id=scope.tenant,
            project_id=scope.project,
            document_type=document_type,
            filename="technical-s7.docx",
            file_format=".docx",
            file_hash=digest,
            created_by=actor.id,
        )
    )
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        DocumentRevisionORM(
            revision_id=revision,
            tenant_id=scope.tenant,
            project_id=scope.project,
            document_id=document,
            rev_no=1,
            blob_hash=digest,
            blob_key=key,
            valid_from=now,
            created_at=now,
        )
    )
    await db.flush()
    db.add(
        DocumentArtifactORM(
            artifact_id=uuid4(),
            tenant_id=scope.tenant,
            project_id=scope.project,
            document_id=document,
            document_revision_id=revision,
            artifact_version=1,
            artifact_hash="a" * 64,
            payload={"doc_type": "technical_spec"},
            trust_state="trusted",
            lifecycle_status="active",
        )
    )
    db.add(
        ClauseORM(
            id=clause,
            tenant_id=scope.tenant,
            project_id=scope.project,
            document_id=document,
            revision_id=revision,
            clause_code="4.1.2",
            title=SOURCE,
            full_text=SOURCE,
            text_start_offset=0,
            text_end_offset=len(SOURCE),
            extracted_entities={
                "technical_requirement": {
                    "source_section": "4.1.2",
                    "verification_status": "unverified",
                },
                "evidence_location": {"revision_id": str(revision)},
            },
            extraction_confidence=None,
            extraction_model="deterministic-technical-section-v1",
            manually_verified=False,
        )
    )
    await db.commit()

    return {
        "tenant": scope.tenant,
        "project": scope.project,
        "actor": actor.id,
        "document": document,
        "revision": revision,
        "clause": clause,
        "digest": digest,
        "baseline": baseline,
        "node": node,
        "reader": ImmutableDocxTechnicalTextReader(
            _ImmutableLocalStorage(file, key)  # type: ignore[arg-type]
        ),
    }


def _arguments(w: dict, **changes: object) -> dict:
    params = {
        "tenant_id": w["tenant"],
        "project_id": w["project"],
        "actor_user_id": w["actor"],
        "clause_id": w["clause"],
        "expected_revision_id": w["revision"],
        "expected_blob_hash": w["digest"],
        "expected_wbs_baseline_id": w["baseline"],
        "proposed_wbs_node_id": w["node"],
        "decision": TechnicalMappingDecision.CONFIRMED_FOR_REVIEW,
        "idempotency_key": "s7-pg-immutable-key",
        "reason": "Verified source section against approved WBS node",
    }
    params.update(changes)
    return params


async def _events(db: AsyncSession, w: dict) -> list[ProjectEventORM]:
    return list(
        (
            await db.scalars(
                select(ProjectEventORM)
                .where(
                    ProjectEventORM.tenant_id == w["tenant"],
                    ProjectEventORM.project_id == w["project"],
                    ProjectEventORM.event_type == EVENT_TYPE,
                )
                .order_by(ProjectEventORM.occurred_at)
            )
        ).all()
    )


@pytest.mark.parametrize(
    ("document_type", "allowed"),
    [
        (DocumentType.TECHNICAL_SPEC, True),
        (DocumentType.SPECIFICATION, True),
        (DocumentType.CONTRACT, False),
    ],
)
async def test_technical_document_families_are_enforced_against_real_postgres(
    db: AsyncSession,
    test_session_factory,
    tmp_path: Path,
    document_type: DocumentType,
    allowed: bool,
) -> None:
    """S2->S7: actual triplet 'specification' works; forged contract source fails."""
    w = await _world(db, tmp_path, document_type)
    async with test_session_factory() as request_session:
        service = RecordTechnicalWBSReviewService(request_session, w["reader"])
        if allowed:
            receipt = await service.execute(**_arguments(w))
            assert receipt.candidate.technical_revision_id == w["revision"]
            assert receipt.candidate.source_clause_id == w["clause"]
            assert receipt.candidate.is_approved_link is False
            await request_session.commit()
        else:
            with pytest.raises(
                TechnicalMappingReviewError,
                match="technical clause or immutable revision not found",
            ):
                await service.execute(**_arguments(w))
            await request_session.rollback()

    async with test_session_factory() as observer:
        events = await _events(observer, w)
        assert len(events) == (1 if allowed else 0)
        if events:
            assert events[0].payload["authority"] == "AUDIT_ONLY_NOT_CANONICAL_LINK"


async def test_real_pg_service_commit_replay_conflict_without_canonical_link(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w = await _world(db, tmp_path)
    async with test_session_factory() as review:
        service = RecordTechnicalWBSReviewService(review, w["reader"])
        first = await service.execute(**_arguments(w))
        assert first.replayed is False
        assert first.candidate.is_approved_link is False
        assert first.candidate.source_section == "4.1.2"
        assert first.candidate.technical_revision_id == w["revision"]
        assert first.candidate.proposed_wbs_baseline_id == w["baseline"]
        await review.commit()

    # Persistence must be visible to an independent PostgreSQL transaction.
    async with test_session_factory() as observer:
        [event] = await _events(observer, w)
        assert event.event_id == first.event_id
        assert event.source_revision_id == w["revision"]
        assert event.actor == f"user:{w['actor']}"
        assert event.payload["source_blob_hash"] == w["digest"]
        assert event.payload["source_section"] == "4.1.2"
        assert event.payload["source_start_offset"] == 0
        assert event.payload["source_end_offset"] == len(SOURCE)
        assert event.payload["wbs_baseline_id"] == str(w["baseline"])
        assert event.payload["wbs_node_id"] == str(w["node"])
        assert event.payload["decision"] == "CONFIRMED_FOR_REVIEW"
        assert event.payload["authority"] == "AUDIT_ONLY_NOT_CANONICAL_LINK"
        assert event.payload["technical_assessment"] == "NOT_ASSESSED"

    async with test_session_factory() as replay:
        service = RecordTechnicalWBSReviewService(replay, w["reader"])
        again = await service.execute(**_arguments(w))
        assert again.replayed is True
        assert again.event_id == first.event_id
        await replay.commit()

    async with test_session_factory() as conflict:
        service = RecordTechnicalWBSReviewService(conflict, w["reader"])
        with pytest.raises(TechnicalMappingReviewError, match="already reviewed"):
            await service.execute(
                **_arguments(w, decision=TechnicalMappingDecision.REJECTED)
            )
        await conflict.rollback()

    async with test_session_factory() as verify:
        assert len(await _events(verify, w)) == 1
        assert (
            await verify.scalar(
                select(func.count()).select_from(WBSNodeORM).where(
                    WBSNodeORM.project_id == w["project"]
                )
            )
        ) == 4
        assert (
            await verify.scalar(
                select(func.count()).select_from(WBSBaselineORM).where(
                    WBSBaselineORM.project_id == w["project"]
                )
            )
        ) == 1
        assert (
            await verify.scalar(
                select(DocumentArtifactORM.trust_state).where(
                    DocumentArtifactORM.document_id == w["document"]
                )
            )
        ) == "trusted"


async def test_real_pg_service_denies_stale_and_foreign_without_event(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w = await _world(db, tmp_path)
    denials = [
        (_arguments(w, actor_user_id=uuid4()), "human reviewer"),
        (_arguments(w, tenant_id=uuid4()), "project unavailable"),
        (_arguments(w, expected_wbs_baseline_id=uuid4()), "baseline changed"),
        (_arguments(w, expected_blob_hash="f" * 64), "revision does not match"),
    ]
    for params, diagnostic in denials:
        async with test_session_factory() as session:
            service = RecordTechnicalWBSReviewService(session, w["reader"])
            with pytest.raises(TechnicalMappingReviewError, match=diagnostic):
                await service.execute(**params)
            await session.rollback()
    async with test_session_factory() as verify:
        assert await _events(verify, w) == []


async def test_http_router_real_service_real_pg_commit_relogin_simulation_and_denials(
    db: AsyncSession, test_session_factory, tmp_path: Path, monkeypatch
) -> None:
    """HTTP -> production session dependency -> real service -> Postgres.

    The only substitutions are a test-owned immutable DOCX storage provider
    and a persisted Clerk-linked principal. NO live Clerk JWT/browser login.
    """
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from src.analysis.adapters.http import technical_wbs_review_router as review_router
    from src.core.auth.dependencies import get_current_user

    w = await _world(db, tmp_path)
    reviewer = await db.get(User, w["actor"])
    assert reviewer is not None
    assert reviewer.clerk_user_id and not reviewer.is_verified

    app = FastAPI()
    app.include_router(review_router.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: reviewer

    # The real HTTP dependency must invoke get_session_with_tenant, which
    # commits on successful response and rolls back on a failing request.
    # test_session_factory already supplies core_database._session_factory.
    # Only the immutable synthetic blob provider and Clerk principal differ.
    monkeypatch.setattr(
        review_router, "build_storage_service", lambda: w["reader"].storage
    )
    endpoint = f"/api/v1/projects/{w['project']}/technical-wbs/reviews"
    body = {
        "clause_id": str(w["clause"]),
        "expected_revision_id": str(w["revision"]),
        "expected_blob_hash": w["digest"],
        "expected_wbs_baseline_id": str(w["baseline"]),
        "proposed_wbs_node_id": str(w["node"]),
        "decision": "CONFIRMED_FOR_REVIEW",
        "idempotency_key": "s7-http-postgres-event-retry",
        "reason": "Confirmed exact technical section for WBS review",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        accepted = await client.post(endpoint, json=body)
        assert accepted.status_code == 201, accepted.text
        receipt = accepted.json()
        assert receipt["replayed"] is False
        assert receipt["authority"] == "AUDIT_ONLY_NOT_CANONICAL_LINK"
        assert receipt["technical_assessment"] == "NOT_ASSESSED"
        assert receipt["approved_canonical_link"] is False
        assert receipt["technical_revision_id"] == str(w["revision"])
        assert receipt["proposed_wbs_baseline_id"] == str(w["baseline"])

    # A distinct DB transaction, not the injected request session, confirms
    # durable authority, actor and exact provenance after the HTTP returns.
    async with test_session_factory() as observer:
        [event] = await _events(observer, w)
        assert str(event.event_id) == receipt["event_id"]
        assert event.actor == f"user:{w['actor']}"
        assert event.payload["source_blob_hash"] == w["digest"]
        assert event.payload["source_clause_id"] == str(w["clause"])
        assert event.payload["reason"] == body["reason"]

    # A new ASGI client emulates a new request/session, NOT Clerk relogin.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        replay = await client.post(endpoint, json=body)
        assert replay.status_code == 201, replay.text
        assert replay.json()["replayed"] is True
        assert replay.json()["event_id"] == receipt["event_id"]

        # A distinct HTTP request, session and DB transaction retrieves only
        # the authenticated reviewer's durable historical fact, never a link.
        history = await client.get(endpoint)
        assert history.status_code == 200, history.text
        [record] = history.json()
        assert record["event_id"] == receipt["event_id"]
        assert record["source_clause_id"] == str(w["clause"])
        assert record["technical_revision_id"] == str(w["revision"])
        assert record["proposed_wbs_baseline_id"] == str(w["baseline"])
        assert record["proposed_wbs_node_id"] == str(w["node"])
        assert record["reason"] == body["reason"]
        assert record["decision"] == "CONFIRMED_FOR_REVIEW"
        assert record["state"] == "HISTORICAL_AUDIT_ONLY"
        assert record["authority"] == "AUDIT_ONLY_NOT_CANONICAL_LINK"
        assert record["approved_canonical_link"] is False

        assert (await client.get(endpoint, params={"limit": 0})).status_code == 422
        assert (await client.get(endpoint, params={"limit": 51})).status_code == 422
        assert (
            await client.get(f"/api/v1/projects/{uuid4()}/technical-wbs/reviews")
        ).status_code == 404

        contradictory = await client.post(endpoint, json={**body, "decision": "REJECTED"})
        assert contradictory.status_code == 409, contradictory.text

        forged = await client.post(endpoint, json={**body, "approved_canonical_link": True})
        assert forged.status_code == 422, forged.text

        foreign_project = await client.post(
            f"/api/v1/projects/{uuid4()}/technical-wbs/reviews", json=body
        )
        assert foreign_project.status_code == 404, foreign_project.text

        stale_hash = await client.post(
            endpoint, json={**body, "expected_blob_hash": "f" * 64}
        )
        assert stale_hash.status_code == 409, stale_hash.text

    # Another actor in the same tenant cannot read the first actor's audit
    # history. The override models only a separately authenticated principal,
    # not a real Clerk login.
    other_reviewer = User(
        id=uuid4(),
        tenant_id=w["tenant"],
        email=f"other-s7-{uuid4().hex}@example.invalid",
        clerk_user_id=f"clerk-other-s7-{uuid4().hex}",
        is_active=True,
        is_verified=False,
    )
    app.dependency_overrides[get_current_user] = lambda: other_reviewer
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        other_history = await client.get(endpoint)
        assert other_history.status_code == 200, other_history.text
        assert other_history.json() == []

    # An unrelated tenant principal must not learn if the first project exists.
    foreign_reviewer = User(
        id=uuid4(),
        tenant_id=uuid4(),
        email=f"foreign-s7-{uuid4().hex}@example.invalid",
        clerk_user_id=f"clerk-foreign-s7-{uuid4().hex}",
        is_active=True,
        is_verified=False,
    )
    app.dependency_overrides[get_current_user] = lambda: foreign_reviewer
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        foreign = await client.post(endpoint, json=body)
        assert foreign.status_code == 404, foreign.text
        foreign_history = await client.get(endpoint)
        assert foreign_history.status_code == 404, foreign_history.text

    async with test_session_factory() as observer:
        assert len(await _events(observer, w)) == 1


async def test_revision_status_exposes_immutable_a_hash_when_document_uploaded_b(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    """S7 + S6: uploaded B's mutable document hash cannot replace trusted A's SHA.

    The revision status response must expose the source revision's immutable
    blob_hash, not documents.file_hash updated by the next upload.
    """
    from src.temporal.adapters.persistence.revision_status_reader import (
        SqlAlchemyRevisionStatusReader,
    )

    world = await _world(db, tmp_path)
    document = await db.get(DocumentORM, world["document"])
    assert document is not None
    document.file_hash = "b" * 64
    await db.commit()
    async with test_session_factory() as observer:
        status = await SqlAlchemyRevisionStatusReader(observer).read(
            tenant_id=world["tenant"],
            project_id=world["project"],
            document_id=world["document"],
            revision_id=world["revision"],
        )
        assert status is not None
        assert status.status == "available"
        assert status.blob_hash == world["digest"]
        assert status.blob_hash != document.file_hash
