"""ADR-032 Q1 / P0: the audited self-approval exception and the fail-closed requester check."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.structured_source_trust import (
    StructuredTrustConflict,
    StructuredTrustForbidden,
    parse_self_approval_exception,
)
from src.temporal.adapters.persistence.models import ProjectEventORM
from tests.modules.integration.test_adr032_structured_source_trust_pg import (
    EXCEPTION,
    KEY,
    _approver,
    _artifact,
    _decide,
    _document,
    _grant,
    _request,
    _Storage,
    _world,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "raw",
    [
        True,
        None,
        {},
        {"enabled": True},
        {**EXCEPTION, "enabled": False},
        {**EXCEPTION, "enabled": "true"},
        {**EXCEPTION, "reason": "   "},
        {**EXCEPTION, "reason": None},
        {**EXCEPTION, "granted_by": ""},
        {**EXCEPTION, "granted_by": None},
        {**EXCEPTION, "granted_at": "not-a-date"},
        {**EXCEPTION, "granted_at": None},
    ],
)
def test_an_incomplete_or_anonymous_exception_is_not_in_force(raw) -> None:
    assert parse_self_approval_exception(raw) is None


def test_a_complete_exception_is_parsed_and_serialisable() -> None:
    parsed = parse_self_approval_exception({**EXCEPTION, "granted_at": "2026-11-01T10:00:00Z"})
    assert parsed is not None and parsed.granted_by == "operator:synthetic-tenant-a"
    assert parsed.as_json()["enabled"] is True and parsed.as_json()["reason"] == EXCEPTION["reason"]


@pytest.mark.parametrize(
    "override",
    [
        {"enabled": False},
        {"reason": None},
        {"granted_by": None},
        {"granted_at": None},
        {"granted_at": "yesterday"},
    ],
)
async def test_self_approval_is_refused_for_every_incomplete_exception(
    db: AsyncSession, test_session_factory, tmp_path: Path, override: dict
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    await _grant(db, w["tenant"], **override)
    with pytest.raises(StructuredTrustForbidden) as refused:
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=w["actor"])
    assert refused.value.code == "SEPARATION_OF_DUTIES_REQUIRED"
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"


async def test_a_bare_boolean_exception_is_anonymous_and_refused(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    from src.core.auth.models import Tenant

    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    await db.execute(
        update(Tenant).where(Tenant.id == w["tenant"]).values(
            settings={
                "hitl_project_authorization": {"mode": "off"},
                "trust_governance": {"structured_source_self_approval": True},
            }
        )
    )
    await db.commit()
    with pytest.raises(StructuredTrustForbidden):
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=w["actor"])


async def test_the_exception_is_per_tenant_and_audited_in_the_decision_event(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    other = await _world(db, tmp_path)  # a second tenant that must NOT inherit the exception
    doc = await _document(db, w, tmp_path, storage)
    other_doc = await _document(db, other, tmp_path, storage)
    await _grant(db, w["tenant"])
    receipt = await _request(test_session_factory, storage, w, doc)
    out = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=w["actor"])
    assert out.self_approved and not out.independent
    async with test_session_factory() as session:
        event = await session.scalar(
            select(ProjectEventORM).where(
                ProjectEventORM.event_id == out.event_id,
            )
        )
        assert event is not None
        payload = event.payload
        assert payload["self_approved"] is True and payload["requester_is_decider"] is True
        assert payload["independent_approval"] is False
        assert payload["self_approval_exception"] == EXCEPTION
        assert payload["requested_by"] == payload["decided_by"] == str(w["actor"])
    other_receipt = await _request(test_session_factory, storage, other, other_doc)
    with pytest.raises(StructuredTrustForbidden):
        await _decide(test_session_factory, storage, other, other_receipt, "APPROVE", actor=other["actor"])


async def test_independent_and_self_rejection_audit(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    out = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert out.independent and not out.self_approved
    other_doc = await _document(db, w, tmp_path, storage, family="schedule")
    other = await _request(test_session_factory, storage, w, other_doc, key=f"{KEY}r3")
    rej = await _decide(test_session_factory, storage, w, other, "REJECT", actor=w["actor"], key=f"{KEY}rj3")
    assert not rej.self_approved and not rej.independent
    async with test_session_factory() as session:
        events = {
            e.event_id: e.payload
            for e in (await session.scalars(select(ProjectEventORM).where(
                ProjectEventORM.event_type == "structured_source.trust_decided",
                ProjectEventORM.project_id == w["project"]))).all()
        }
    assert events[out.event_id]["separation_of_duties"] == "SEPARATED"
    assert events[out.event_id]["self_approval_exception"] is None
    assert events[rej.event_id]["separation_of_duties"] == "SELF_REJECTION"
    assert events[rej.event_id]["self_approved"] is False


# Fail-closed requester -----------------------------------------------------------------------
async def _tamper_request_event(factory, artifact_id, mutate) -> None:
    """Simulate a corrupted audit trail (the table is append-only, so triggers are bypassed for
    this test session only via session_replication_role)."""
    async with factory() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        event = await session.scalar(select(ProjectEventORM).where(
            ProjectEventORM.event_type == "structured_source.trust_requested",
            ProjectEventORM.payload["artifact_id"].astext == str(artifact_id)))
        assert event is not None
        mutate(event)
        await session.commit()


async def test_a_decision_without_a_trust_requested_event_fails_closed(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    """A candidate that reached PROPOSED without the audited request (e.g. written by another path)
    cannot be decided: the requester is unknown, so separation of duties is unverifiable."""
    from src.analysis.adapters.persistence.document_artifact_repository import (
        SqlAlchemyDocumentArtifactRepository,
    )
    from src.analysis.application.structured_source_trust import (
        PARSER_ID,
        PARSER_VERSION,
        ImmutableStructuredSourceVerifier,
        content_digest_of,
    )
    from src.analysis.domain.contracts import DocumentArtifact, StructuredSource
    from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    verified = await ImmutableStructuredSourceVerifier(storage, ExcelFileParser()).verify(  # type: ignore[arg-type]
        revision=await _revision_of(test_session_factory, w, doc), family="budget"
    )
    _ = content_digest_of
    async with test_session_factory() as session:
        binding, review_id = await SqlAlchemyDocumentArtifactRepository(session).save_structured_candidate(
            DocumentArtifact(
                document_id=str(doc["document"]), document_revision_id=str(doc["revision"]),
                doc_type="budget",
                structured_source=StructuredSource(
                    family="budget", blob_sha256=verified.blob_sha256, parser_id=PARSER_ID,
                    parser_version=PARSER_VERSION, row_count=verified.row_count,
                    content_digest=verified.content_digest),
            ),
            project_id=w["project"], tenant_id=w["tenant"],
        )
        await session.commit()
    receipt = SimpleNamespace(
        review_row_id=review_id, artifact_id=binding.artifact_id,
        artifact_version=binding.artifact_version, artifact_hash=binding.artifact_hash,
    )
    for decision in ("APPROVE", "REJECT"):
        with pytest.raises(StructuredTrustConflict) as refused:
            await _decide(test_session_factory, storage, w, receipt, decision, actor=approver, key=f"{KEY}{decision}")
        assert refused.value.code == "request_event_missing"
    assert (await _artifact(test_session_factory, binding.artifact_id)).trust_state == "proposed"
    assert await db.scalar(text("SELECT count(*) FROM project_events WHERE event_type = "
                                "'structured_source.trust_decided' AND project_id = cast(:p as uuid)"),
                           {"p": str(w["project"])}) == 0


async def _revision_of(factory, w, doc):
    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )

    async with factory() as session:
        revision = await SqlAlchemyDocumentRevisionRepository(session).get_by_id(doc["revision"], w["tenant"])
    assert revision is not None
    return revision


@pytest.mark.parametrize(
    "mutation",
    [
        "requester_unknown_user",
        "requester_missing",
        "actor_disagrees",
        "wrong_hash",
        "wrong_document",
        "wrong_review",
        "no_source_revision",
        "requester_not_uuid",
    ],
)
async def test_an_inconsistent_trust_requested_event_fails_closed(
    db: AsyncSession, test_session_factory, tmp_path: Path, mutation: str
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)

    def mutate(event: ProjectEventORM) -> None:
        payload = dict(event.payload)
        if mutation == "requester_unknown_user":
            ghost = str(uuid4())
            payload["requested_by"] = ghost
            event.actor = f"user:{ghost}"
        elif mutation == "requester_missing":
            payload.pop("requested_by")
        elif mutation == "actor_disagrees":
            event.actor = f"user:{uuid4()}"
        elif mutation == "wrong_hash":
            payload["artifact_hash"] = "0" * 64
        elif mutation == "wrong_document":
            payload["document_id"] = str(uuid4())
        elif mutation == "wrong_review":
            payload["review_row_id"] = str(uuid4())
        elif mutation == "no_source_revision":
            event.source_revision_id = None
        else:
            payload["requested_by"] = "not-a-uuid"
            event.actor = "user:not-a-uuid"
        event.payload = payload

    await _tamper_request_event(test_session_factory, receipt.artifact_id, mutate)
    with pytest.raises(StructuredTrustConflict) as refused:
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert refused.value.code == "request_event_inconsistent"
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"


async def test_duplicate_request_events_fail_closed(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    from datetime import UTC, datetime

    from src.temporal.adapters.persistence.project_event_repository import (
        SqlAlchemyProjectEventRepository,
    )
    from src.temporal.domain.project_event import ProjectEvent

    async with test_session_factory() as session:
        original = await session.scalar(select(ProjectEventORM).where(
            ProjectEventORM.event_type == "structured_source.trust_requested",
            ProjectEventORM.project_id == w["project"]))
        assert original is not None
        now = datetime.now(UTC).replace(tzinfo=None)
        await SqlAlchemyProjectEventRepository(session).append(ProjectEvent(
            event_id=uuid4(), tenant_id=w["tenant"], project_id=w["project"],
            source_revision_id=original.source_revision_id, event_type=original.event_type,
            occurred_at=now, created_at=now, actor=original.actor, payload=dict(original.payload)))
        await session.commit()
    with pytest.raises(StructuredTrustConflict) as refused:
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert refused.value.code == "request_event_inconsistent"
