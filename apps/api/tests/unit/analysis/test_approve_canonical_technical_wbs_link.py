"""S7 canonical Technical -> WBS writer: explicit approval and current-authority gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.analysis.application import approve_canonical_technical_wbs_link as target
from src.temporal.domain.current_revision import CurrentRevision, CurrentRevisionStatus
from src.temporal.domain.document_revision import DocumentRevision
from src.wbs.domain.governance import AuthorityState, WBSAuthority

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PROJECT = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT = UUID("33333333-3333-3333-3333-333333333333")
REVISION = UUID("44444444-4444-4444-4444-444444444444")
CLAUSE = UUID("55555555-5555-5555-5555-555555555555")
NODE = UUID("66666666-6666-6666-6666-666666666666")
BASELINE = UUID("77777777-7777-7777-7777-777777777777")
ACTOR = UUID("88888888-8888-8888-8888-888888888888")
NOW = datetime(2026, 10, 29, tzinfo=UTC)


@dataclass
class _Audit:
    event_id: UUID
    payload: dict[str, object]


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _Session:
    def __init__(self, *, project=True, review=None, existing=None):
        self.project = project
        self.review = review or _audit()
        self.existing = existing
        self.events = []

    async def scalar(self, query, params=None):
        if params and "project" in params:
            return PROJECT if self.project else None
        entity = query.column_descriptions[0].get("entity")
        if entity is target.User:
            return ACTOR
        if entity is target.ProjectEventORM:
            return self.review
        raise AssertionError(f"unexpected scalar query: {query}")

    async def execute(self, query):
        return _Result(self.existing)


def _audit(*, decision="CONFIRMED_FOR_REVIEW", baseline=BASELINE, node=NODE):
    return _Audit(
        event_id=uuid4(),
        payload={
            "authority": "AUDIT_ONLY_NOT_CANONICAL_LINK",
            "technical_assessment": "NOT_ASSESSED",
            "decision": decision,
            "technical_document_id": str(DOCUMENT),
            "technical_revision_id": str(REVISION),
            "source_clause_id": str(CLAUSE),
            "source_section": "4.1.2",
            "source_start_offset": 0,
            "source_end_offset": 42,
            "source_blob_hash": "a" * 64,
            "wbs_baseline_id": str(baseline),
            "wbs_node_id": str(node),
        },
    )


def _revision():
    return DocumentRevision(
        revision_id=REVISION,
        document_id=DOCUMENT,
        project_id=PROJECT,
        tenant_id=TENANT,
        rev_no=1,
        blob_hash="a" * 64,
        blob_key="revisions/spec.docx",
        valid_from=NOW,
        created_at=NOW,
    )


def _patch(monkeypatch, session, *, baseline=BASELINE, status=CurrentRevisionStatus.TRUSTED):
    async def authority(*args, **kwargs):
        assert kwargs["node_ids"] == {NODE}
        return WBSAuthority(
            state=AuthorityState.APPROVED_BASELINE,
            baseline_id=baseline,
            baseline_no=1,
            tree_digest="a" * 64,
            applied_at=NOW,
            open_change_sets=0,
            legacy_node_count=0,
        )

    async def locked(*args, **kwargs):
        assert kwargs["revision_id"] == REVISION
        return REVISION

    class Revisions:
        def __init__(self, db):
            assert db is session

        async def get_by_id(self, revision_id, tenant_id):
            assert (revision_id, tenant_id) == (REVISION, TENANT)
            return _revision()

    class Current:
        def __init__(self, db):
            assert db is session

        async def resolve(self, *, tenant_id, document_id):
            return CurrentRevision(
                document_id=DOCUMENT,
                revision_id=REVISION,
                status=status,
                single_revision=True,
            )

    class Events:
        def __init__(self, db):
            assert db is session

        async def append(self, event):
            session.events.append(event)
            return event

    monkeypatch.setattr(target, "require_linkable_wbs_nodes", authority)
    monkeypatch.setattr(target, "require_locked_trusted_artifact", locked)
    monkeypatch.setattr(target, "SqlAlchemyDocumentRevisionRepository", Revisions)
    monkeypatch.setattr(target, "SqlAlchemyCurrentRevisionResolver", Current)
    monkeypatch.setattr(target, "SqlAlchemyProjectEventRepository", Events)


async def _approve(session, **overrides):
    args = {
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "actor_user_id": ACTOR,
        "review_event_id": session.review.event_id,
        "expected_wbs_baseline_id": BASELINE,
        "expected_wbs_node_id": NODE,
        "approval": target.CANONICAL_APPROVAL,
        "idempotency_key": "canonical-link-key-A",
        "reason": "Engineer explicitly approves the current source-to-WBS association",
    }
    args.update(overrides)
    return await target.ApproveCanonicalTechnicalWBSLinkService(session).execute(**args)


@pytest.mark.asyncio
async def test_explicit_human_approval_persists_distinct_canonical_event(monkeypatch):
    session = _Session()
    _patch(monkeypatch, session)

    result = await _approve(session)

    assert result.replayed is False
    assert len(session.events) == 1
    event = session.events[0]
    assert event.event_type == target.CANONICAL_LINK_EVENT
    assert event.actor == f"user:{ACTOR}"
    assert event.payload["review_event_id"] == str(session.review.event_id)
    assert event.payload["authority"] == "EXPLICIT_HUMAN_CANONICAL_LINK"
    assert event.payload["approval"] == target.CANONICAL_APPROVAL
    assert event.payload["wbs_baseline_id"] == str(BASELINE)
    assert event.payload["wbs_node_id"] == str(NODE)
    assert event.occurred_at.tzinfo is None


@pytest.mark.asyncio
async def test_replay_is_idempotent_and_conflicting_approval_is_refused(monkeypatch):
    session = _Session()
    _patch(monkeypatch, session)
    first = await _approve(session)
    session.existing = type(
        "Existing",
        (),
        {
            "event_id": first.event_id,
            "actor": f"user:{ACTOR}",
            "payload": session.events[0].payload,
        },
    )()

    replay = await _approve(session)
    assert replay.replayed is True
    assert replay.event_id == first.event_id

    with pytest.raises(target.CanonicalTechnicalWBSLinkError, match="already settled"):
        await _approve(session, reason="different human decision")
    assert len(session.events) == 1


@pytest.mark.asyncio
async def test_audit_only_or_rejected_review_never_becomes_canonical(monkeypatch):
    session = _Session(review=_audit(decision="REJECTED"))
    _patch(monkeypatch, session)

    with pytest.raises(target.CanonicalTechnicalWBSLinkError, match="does not authorize"):
        await _approve(session)
    assert session.events == []


@pytest.mark.asyncio
async def test_explicit_approval_and_current_authority_are_required(monkeypatch):
    session = _Session()
    _patch(monkeypatch, session, baseline=uuid4())

    with pytest.raises(target.CanonicalTechnicalWBSLinkError, match="explicit canonical approval"):
        await _approve(session, approval="AUDIT_ONLY_NOT_CANONICAL_LINK")
    with pytest.raises(target.CanonicalTechnicalWBSLinkError, match="baseline changed"):
        await _approve(session)
    assert session.events == []


@pytest.mark.asyncio
async def test_stale_trusted_revision_is_rejected(monkeypatch):
    session = _Session()
    _patch(monkeypatch, session, status=CurrentRevisionStatus.SINGLE_REVISION)

    with pytest.raises(target.CanonicalTechnicalWBSLinkError, match="source revision is stale"):
        await _approve(session)
    assert session.events == []


@pytest.mark.asyncio
async def test_foreign_or_missing_project_is_neutral_failure(monkeypatch):
    session = _Session(project=False)
    _patch(monkeypatch, session)

    with pytest.raises(target.CanonicalTechnicalWBSLinkError, match="project unavailable"):
        await _approve(session)
    assert session.events == []
