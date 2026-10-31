"""S7 authority regression: one original XLSX row, one approved WBS, one human event.

Unit lane intentionally exercises production service branches included in combined
Codecov; the separate PostgreSQL S7 test remains the persistence integration gate.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from src.analysis.application import canonical_structured_wbs_links as target
from src.temporal.domain.current_revision import CurrentRevisionStatus

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PROJECT = UUID("22222222-2222-2222-2222-222222222222")
ACTOR = UUID("33333333-3333-3333-3333-333333333333")
DOC = UUID("44444444-4444-4444-4444-444444444444")
REV = UUID("55555555-5555-5555-5555-555555555555")
BASE = UUID("66666666-6666-6666-6666-666666666666")
NODE = UUID("77777777-7777-7777-7777-777777777777")
HASH = "a" * 64
LOCATOR = "Sheet1!row:4"


class FakeSession:
    def __init__(self, *, human=True, document=True, project=True, existing=None):
        self.human = human
        self.document = document
        self.project = project
        self.existing = existing
        self.events = []
        self.reads = []

    async def scalar(self, query, params=None):
        if params is not None and "p" in params and "t" in params:
            self.reads.append("project")
            return PROJECT if self.project else None
        entity = query.column_descriptions[0].get("entity")
        if entity is target.User:
            self.reads.append("human")
            return ACTOR if self.human else None
        if entity is target.DocumentORM:
            self.reads.append("document")
            return SimpleNamespace(id=DOC) if self.document else None
        if entity is target.ProjectEventORM:
            self.reads.append("event")
            return self.existing
        raise AssertionError(f"unexpected query {query}")


class RowReader:
    def __init__(self, *, wrong_node=False):
        self.wrong_node = wrong_node
        self.read_count = 0

    async def read_row(self, *, revision, family, source_locator):
        assert revision.document_id == DOC
        assert (family, source_locator) == ("budget", LOCATOR)
        self.read_count += 1
        return {"source_locator": LOCATOR, "description": "Earthworks excavation",
                "quantity": "1250", "wbs_node_id": str(UUID(int=9) if self.wrong_node else NODE)}


def fixture(monkeypatch, *, baseline=BASE, current=True, trusted=True, row_wrong_node=False, **session_options):
    session = FakeSession(**session_options)
    reader = RowReader(wrong_node=row_wrong_node)

    async def require_authority(db, *, tenant_id, project_id, node_ids):
        assert (db, tenant_id, project_id, node_ids) == (session, TENANT, PROJECT, {NODE})
        return SimpleNamespace(baseline_id=baseline)

    async def lock_trust(db, **kwargs):
        assert db is session and kwargs["revision_id"] == REV
        if not trusted:
            raise target.TechnicalMappingReviewError("trust invalid")
        return REV

    class Revisions:
        def __init__(self, db): assert db is session
        async def get_by_id(self, revision_id, tenant_id):
            assert (revision_id, tenant_id) == (REV, TENANT)
            return SimpleNamespace(document_id=DOC, project_id=PROJECT, blob_hash=HASH)

    class Current:
        def __init__(self, db): assert db is session
        async def resolve(self, *, tenant_id, document_id):
            assert (tenant_id, document_id) == (TENANT, DOC)
            return SimpleNamespace(status=CurrentRevisionStatus.TRUSTED if current else CurrentRevisionStatus.SINGLE_REVISION,
                                   revision_id=REV if current else UUID(int=10))

    class Events:
        def __init__(self, db): assert db is session
        async def append(self, event):
            session.events.append(event)
            return event

    monkeypatch.setattr(target, "require_linkable_wbs_nodes", require_authority)
    monkeypatch.setattr(target, "require_locked_trusted_artifact", lock_trust)
    monkeypatch.setattr(target, "SqlAlchemyDocumentRevisionRepository", Revisions)
    monkeypatch.setattr(target, "SqlAlchemyCurrentRevisionResolver", Current)
    monkeypatch.setattr(target, "SqlAlchemyProjectEventRepository", Events)
    return session, reader


async def approve(session, reader, **overrides):
    data = dict(tenant_id=TENANT, project_id=PROJECT, actor_user_id=ACTOR,
                family="budget", source_document_id=DOC, source_revision_id=REV,
                expected_blob_hash=HASH, source_locator=LOCATOR,
                expected_wbs_baseline_id=BASE, expected_wbs_node_id=NODE,
                approval=target.APPROVAL, idempotency_key="human-approval-001",
                reason="Engineer verified the original budget row and the approved baseline")
    data.update(overrides)
    return await target.ApproveStructuredWBSLinkService(session, reader).execute(**data)


@pytest.mark.asyncio
async def test_current_trusted_row_requires_human_and_appends_only_canonical_link_event(monkeypatch):
    session, reader = fixture(monkeypatch)
    result = await approve(session, reader)
    assert result.replayed is False
    assert result.wbs_baseline_id == BASE and result.wbs_node_id == NODE
    assert result.source_revision_id == REV
    assert reader.read_count == 1
    assert len(session.events) == 1
    event = session.events[0]
    assert event.event_type == "budget.wbs_link_approved"
    assert event.source_revision_id == REV
    assert event.actor == f"user:{ACTOR}"
    assert event.payload["authority"] == "EXPLICIT_HUMAN_CANONICAL_LINK"
    assert event.payload["source_assessment"] == "NOT_ASSESSED"
    assert event.payload["source_fingerprint"] == target._fingerprint({
        "source_locator": LOCATOR, "description": "Earthworks excavation",
        "quantity": "1250", "wbs_node_id": str(NODE),
    })


@pytest.mark.parametrize(("options", "message"), [
    ({"human": False}, "authenticated human approver required"),
    ({"project": False}, "project unavailable to tenant"),
    ({"document": False}, "source document/revision/hash unavailable"),
    ({"baseline": UUID(int=2)}, "approved WBS baseline changed"),
    ({"trusted": False}, "source revision is not trusted"),
    ({"current": False}, "source revision is not current trusted"),
    ({"row_wrong_node": True}, "source WBS node ID disagrees"),
])
@pytest.mark.asyncio
async def test_fail_closed_for_missing_authority_stale_source_and_wbs(monkeypatch, options, message):
    session, reader = fixture(monkeypatch, **options)
    with pytest.raises(target.StructuredWBSLinkError, match=message):
        await approve(session, reader)
    assert session.events == []  # No canonical link approved on failed authority


@pytest.mark.parametrize(("change", "message"), [
    ({"approval": "AUDIT_ONLY_NOT_CANONICAL_LINK"}, "explicit typed human approval"),
    ({"family": "unknown"}, "explicit typed human approval"),
    ({"idempotency_key": "short"}, "bounded reason and idempotency"),
    ({"reason": " "}, "bounded reason and idempotency"),
    ({"source_locator": ""}, "invalid immutable source identity"),
    ({"expected_blob_hash": "bad"}, "invalid immutable source identity"),
])
@pytest.mark.asyncio
async def test_invalid_explicit_consent_or_source_identity_rejected_before_sql(monkeypatch, change, message):
    session, reader = fixture(monkeypatch)
    with pytest.raises(target.StructuredWBSLinkError, match=message):
        await approve(session, reader, **change)
    assert session.reads == []
    assert reader.read_count == 0
    assert session.events == []
