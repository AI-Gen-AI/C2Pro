"""What Changed? timeline shows revision outcomes, never bookkeeping as false results.

Refers to Suite ID: TS-INT-P0C-TIMELINE-002.

The append-only log also holds bookkeeping events: every upload appends ``revision.ingested``
and every analysed contract revision appends a ``revision.analyzed`` snapshot. Rendered as
timeline items they were false: an ingestion stayed "Revision is being compared" forever
after analysis finished, and every ready snapshot — including a first version that had
nothing to compare — showed "No material change found".

The timeline page therefore returns, per revision, only honest user-facing outcomes:
- ``revision.changed`` / ``revision.reinterpreted`` (a real comparison result);
- ``revision.analysis_failed`` (an error, never a no-change);
- ``revision.analyzed`` with state ``needs_review`` (no reliable comparison possible);
- ``revision.ingested`` only while a CONTRACT revision has no outcome yet (processing).
Nothing is deleted: the events stay in the log, the read model just does not misstate them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.core.auth.models import SubscriptionPlan, Tenant
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_projection import (
    build_change_projection_event,
    build_revision_processing_failed_event,
)
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.domain.revision_event_factory import build_revision_ingested_event

pytestmark = pytest.mark.asyncio

_T0 = datetime(2026, 9, 14, 9, 0, tzinfo=UTC).replace(tzinfo=None)


async def _project(db: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id, project_id = uuid4(), uuid4()
    db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                  subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0))
    await db.commit()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
             "VALUES (:id, :tid, 'timeline', :code, 'construction', 'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, project_id


async def _document(db: AsyncSession, tenant_id: UUID, project_id: UUID, document_type: str) -> UUID:
    document_id = uuid4()
    await db.execute(
        text("INSERT INTO documents (id, tenant_id, project_id, document_type, filename, upload_status, version, "
             "storage_encrypted, document_metadata, created_at, updated_at) VALUES "
             "(:id, :tid, :pid, :dtype, 'f.pdf', 'uploaded', 1, true, '{}'::jsonb, now(), now())"),
        {"id": document_id, "tid": tenant_id, "pid": project_id, "dtype": document_type},
    )
    await db.commit()
    return document_id


def _at(event: ProjectEvent, minutes: int) -> ProjectEvent:
    moment = _T0 + timedelta(minutes=minutes)
    return event.model_copy(update={"occurred_at": moment, "created_at": moment})


async def _revision(db: AsyncSession, tenant_id: UUID, project_id: UUID, document_id: UUID, rev_no: int,
                    parent: DocumentRevision | None, minutes: int) -> DocumentRevision:
    moment = _T0 + timedelta(minutes=minutes)
    revision = DocumentRevision(
        revision_id=uuid4(), document_id=document_id, project_id=project_id, tenant_id=tenant_id, rev_no=rev_no,
        parent_revision_id=parent.revision_id if parent else None, blob_hash=f"{rev_no:064x}",
        blob_key=f"tenants/{tenant_id}/projects/{project_id}/documents/{document_id}/revisions/{rev_no:064x}.pdf",
        valid_from=moment, created_at=moment,
    )
    repo = SqlAlchemyDocumentRevisionRepository(db)
    if parent is not None:
        await repo.close_current(document_id, tenant_id, moment)
    await repo.append_revision(revision)
    await db.commit()
    return revision


def _ingested(revision: DocumentRevision, minutes: int) -> ProjectEvent:
    return _at(build_revision_ingested_event(
        document_id=revision.document_id, project_id=revision.project_id, tenant_id=revision.tenant_id,
        revision=revision, filename="f.pdf", actor=None,
    ), minutes)


def _analyzed(revision: DocumentRevision, minutes: int, state: str = "ready") -> ProjectEvent:
    return _at(ProjectEvent(
        event_id=uuid4(), project_id=revision.project_id, tenant_id=revision.tenant_id,
        event_type="revision.analyzed", source_revision_id=revision.revision_id,
        payload={"schema_version": 1, "state": state, "document_id": str(revision.document_id),
                 "revision_id": str(revision.revision_id), "blob_hash": revision.blob_hash, "clauses": []},
        occurred_at=_T0, created_at=_T0,
    ), minutes)


def _changed(parent: DocumentRevision, revision: DocumentRevision, minutes: int) -> ProjectEvent:
    changeset = ChangeSet(
        changeset_id=uuid4(), project_id=revision.project_id, tenant_id=revision.tenant_id,
        from_revision_id=parent.revision_id, to_revision_id=revision.revision_id,
        changes=[SemanticChange(object_type="clause", change_type="modified", anchor="AUTO-002",
                                before={"full_text": "2,400,000.00 EUR"}, after={"full_text": "2,650,000.00 EUR"},
                                semantic_summary="price changed", match_confidence=1.0)],
        created_at=_T0,
    )
    return _at(build_change_projection_event(
        changeset=changeset, document_id=revision.document_id,
        source_blob_hash=parent.blob_hash, target_blob_hash=revision.blob_hash,
    ), minutes)


async def test_timeline_shows_revision_outcomes_not_bookkeeping(db: AsyncSession) -> None:
    tenant_id, project_id = await _project(db)
    contract = await _document(db, tenant_id, project_id, "contract")
    budget = await _document(db, tenant_id, project_id, "budget")
    events = SqlAlchemyProjectEventRepository(db)

    rev_a = await _revision(db, tenant_id, project_id, contract, 1, None, 0)
    rev_b = await _revision(db, tenant_id, project_id, contract, 2, rev_a, 10)
    rev_c = await _revision(db, tenant_id, project_id, contract, 3, rev_b, 20)
    budget_rev = await _revision(db, tenant_id, project_id, budget, 1, None, 30)
    other_contract = await _document(db, tenant_id, project_id, "contract")
    failed_rev = await _revision(db, tenant_id, project_id, other_contract, 1, None, 40)
    review_rev = await _revision(db, tenant_id, project_id, other_contract, 2, failed_rev, 50)

    written = [
        _ingested(rev_a, 1), _analyzed(rev_a, 2),                        # genesis: nothing to compare
        _ingested(rev_b, 11), _analyzed(rev_b, 12), _changed(rev_a, rev_b, 12),  # real business change
        _ingested(rev_c, 21),                                             # still processing
        _ingested(budget_rev, 31),                                        # non-contract: no comparison ever
        _ingested(failed_rev, 41),
        _at(build_revision_processing_failed_event(revision=failed_rev, failure_code="analysis_processing_failed"), 42),
        _ingested(review_rev, 51), _analyzed(review_rev, 52, state="needs_review"),
    ]
    for event in written:
        await events.append(event)
    await db.commit()
    expected_visible = {written[4].event_id, written[5].event_id, written[8].event_id, written[10].event_id}

    page = await events.page_for_project(project_id, tenant_id, after=None, limit=50)

    assert {event.event_id for event in page} == expected_visible
    assert [event.event_type for event in page] == [
        "revision.changed", "revision.ingested", "revision.analysis_failed", "revision.analyzed",
    ]
    # The log itself is untouched: every event is still there.
    assert len(await events.list_for_project(project_id, tenant_id)) == len(written)


async def test_timeline_visibility_keeps_keyset_paging_complete(db: AsyncSession) -> None:
    tenant_id, project_id = await _project(db)
    contract = await _document(db, tenant_id, project_id, "contract")
    events = SqlAlchemyProjectEventRepository(db)
    parent = await _revision(db, tenant_id, project_id, contract, 1, None, 0)
    await events.append(_ingested(parent, 1))
    await events.append(_analyzed(parent, 2))
    visible: list[UUID] = []
    for number in range(2, 6):
        revision = await _revision(db, tenant_id, project_id, contract, number, parent, number * 10)
        await events.append(_ingested(revision, number * 10 + 1))
        await events.append(_analyzed(revision, number * 10 + 2))
        change = _changed(parent, revision, number * 10 + 2)
        await events.append(change)
        visible.append(change.event_id)
        parent = revision
    await db.commit()

    first = await events.page_for_project(project_id, tenant_id, after=None, limit=2)
    from src.temporal.application.timeline import TimelineKey

    cursor = TimelineKey(first[1].occurred_at, first[1].event_id)
    second = await events.page_for_project(project_id, tenant_id, after=cursor, limit=2)
    # limit + 1 rows signal a next page; only visible outcomes are ever counted or returned.
    assert [event.event_id for event in first[:2]] + [event.event_id for event in second[:2]] == visible
