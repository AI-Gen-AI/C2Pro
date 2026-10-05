"""C3b-2 - governed append-only recomputation of legacy comparisons (real PostgreSQL).

Refers to Suite ID: TS-INT-C3B2-RECOMPUTE-001 (C3b-2 tests 1-6).

A ``revision.changed`` produced by the older ``p0c-structural-l1-v1`` matcher is
recomputed by the CURRENT matcher over the exact immutable ``revision.analyzed``
snapshots it used, and appended as a NEW ``revision.recomputed`` event:

1. the original row is never mutated (byte-identical payload) and stays readable;
2. provenance names the original event, its engine, and the evidence used;
3. the effective reader returns the recomputation, never the legacy original;
4. idempotent: a re-run, a duplicate delivery, or two concurrent runs leave
   exactly ONE recomputed event (deterministic id + primary key);
5. a recomputation for another tenant/project sees nothing;
6. missing evidence is reported NOT_RECOMPUTABLE, nothing is fabricated.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.change_intelligence.application.structural_diff import diff_contract_revisions
from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.core.auth.models import SubscriptionPlan, Tenant
from src.core.tasks.temporal_tasks import recompute_project_legacy_changes
from src.documents.domain.models import Clause, ClauseType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_projection import (
    CHANGE_PROJECTION_ENGINE_VERSION,
    build_change_projection_event,
)
from src.temporal.application.change_qualification import qualify_event
from src.temporal.application.effective_change import select_effective_outcome
from src.temporal.application.legacy_recomputation import (
    RecomputeStatus,
    recomputation_event_id,
    recompute_legacy_change_event,
    recompute_legacy_changes_for_project,
)
from src.temporal.application.revision_change_orchestrator import _snapshot_clause
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.engine_registry import MatcherStatus
from src.temporal.domain.project_event import ProjectEvent

pytestmark = pytest.mark.asyncio

LEGACY = "p0c-structural-l1-v1"
_T0 = datetime(2026, 9, 20, 9, 0, tzinfo=UTC).replace(tzinfo=None)
V1_TEXT = "Clause 14.2 The contractor pays a delay penalty of 1% per week of delay."
V2_TEXT = "Clause 14.2 The contractor pays a delay penalty of 5% per week of delay."


def _dsn(db: AsyncSession) -> str:
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def independent_sessions(db: AsyncSession) -> AsyncIterator[Any]:
    """Sessions on their OWN engine: genuinely separate transactions."""
    engine = create_async_engine(_dsn(db), pool_size=5, max_overflow=5)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def factory(tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)}
            )
            yield session

    try:
        yield factory
    finally:
        await engine.dispose()


class _World:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.events = SqlAlchemyProjectEventRepository(db)

    async def project(self) -> tuple[UUID, UUID, UUID]:
        tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()
        self.db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                           subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0))
        await self.db.commit()
        await self.db.execute(
            text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, "
                 "updated_at) VALUES (:id, :tid, 'recompute', :code, 'construction', 'active', 'EUR', now(), now())"),
            {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
        )
        await self.db.execute(
            text("INSERT INTO documents (id, tenant_id, project_id, document_type, filename, upload_status, version, "
                 "storage_encrypted, document_metadata, created_at, updated_at) VALUES "
                 "(:id, :tid, :pid, 'contract', 'c.pdf', 'uploaded', 1, true, '{}'::jsonb, now(), now())"),
            {"id": document_id, "tid": tenant_id, "pid": project_id},
        )
        await self.db.commit()
        return tenant_id, project_id, document_id

    async def revision(self, tenant_id: UUID, project_id: UUID, document_id: UUID, rev_no: int,
                       parent: DocumentRevision | None) -> DocumentRevision:
        moment = _T0 + timedelta(minutes=10 * rev_no)
        revision = DocumentRevision(
            revision_id=uuid4(), document_id=document_id, project_id=project_id, tenant_id=tenant_id,
            rev_no=rev_no, parent_revision_id=parent.revision_id if parent else None,
            blob_hash=f"{rev_no:064x}", blob_key=f"r/{document_id}/{rev_no}", valid_from=moment, created_at=moment,
        )
        repo = SqlAlchemyDocumentRevisionRepository(self.db)
        if parent is not None:
            await repo.close_current(document_id, tenant_id, moment)
        await repo.append_revision(revision)
        await self.db.commit()
        return revision

    @staticmethod
    def snapshot(revision: DocumentRevision, body: str, *, minutes: int) -> ProjectEvent:
        moment = _T0 + timedelta(minutes=minutes)
        clause = Clause(
            id=uuid4(), project_id=revision.project_id, tenant_id=revision.tenant_id,
            document_id=revision.document_id, clause_code="14.2", clause_type=ClauseType.PENALTY,
            title="Delay penalty", full_text=body, extracted_entities={},
        )
        return ProjectEvent(
            event_id=uuid4(), project_id=revision.project_id, tenant_id=revision.tenant_id,
            event_type="revision.analyzed", source_revision_id=revision.revision_id,
            payload={"schema_version": 1, "state": "ready", "document_id": str(revision.document_id),
                     "revision_id": str(revision.revision_id), "blob_hash": revision.blob_hash,
                     "clauses": [_snapshot_clause(clause)]},
            occurred_at=moment, created_at=moment,
        )

    @staticmethod
    def legacy_change(v1: DocumentRevision, v2: DocumentRevision, *, minutes: int) -> ProjectEvent:
        """What the v1 matcher stored: an unpaired removed + added for one amended clause."""
        moment = _T0 + timedelta(minutes=minutes)
        changeset = ChangeSet(
            changeset_id=uuid4(), project_id=v2.project_id, tenant_id=v2.tenant_id,
            from_revision_id=v1.revision_id, to_revision_id=v2.revision_id,
            changes=[
                SemanticChange(object_type="clause", change_type="removed", anchor="AUTO-001",
                               before={"full_text": V1_TEXT}, after=None, semantic_summary="removed",
                               match_confidence=0.0),
                SemanticChange(object_type="clause", change_type="added", anchor="AUTO-002",
                               before=None, after={"full_text": V2_TEXT}, semantic_summary="added",
                               match_confidence=0.0),
            ],
            created_at=moment,
        )
        event = build_change_projection_event(
            changeset=changeset, document_id=v2.document_id,
            source_blob_hash=v1.blob_hash, target_blob_hash=v2.blob_hash, diff_engine_version=LEGACY,
        )
        return event.model_copy(update={"occurred_at": moment, "created_at": moment})

    async def legacy_history(self) -> tuple[UUID, UUID, UUID, DocumentRevision, ProjectEvent]:
        tenant_id, project_id, document_id = await self.project()
        v1 = await self.revision(tenant_id, project_id, document_id, 1, None)
        v2 = await self.revision(tenant_id, project_id, document_id, 2, v1)
        await self.events.append(self.snapshot(v1, V1_TEXT, minutes=11))
        await self.events.append(self.snapshot(v2, V2_TEXT, minutes=21))
        original = await self.events.append(self.legacy_change(v1, v2, minutes=22))
        await self.db.commit()
        return tenant_id, project_id, document_id, v2, original

    async def raw_payload(self, event_id: UUID) -> Any:
        row = (await self.db.execute(
            text("SELECT payload::text AS p, occurred_at, event_type FROM project_events WHERE event_id = :e"),
            {"e": event_id},
        )).one()
        return (row.p, row.occurred_at, row.event_type)

    async def count_recomputed(self, tenant_id: UUID) -> int:
        return int((await self.db.execute(
            select(func.count()).select_from(ProjectEventORM).where(
                ProjectEventORM.tenant_id == tenant_id,
                ProjectEventORM.event_type == "revision.recomputed",
            )
        )).scalar_one())


async def test_legacy_comparison_is_recomputed_append_only_with_provenance(db: AsyncSession) -> None:
    world = _World(db)
    tenant_id, project_id, document_id, v2, original = await world.legacy_history()
    before = await world.raw_payload(original.event_id)
    assert qualify_event(original).matcher_status is MatcherStatus.LEGACY

    outcome = await recompute_legacy_change_event(world.events, original)
    await db.commit()

    assert outcome.status is RecomputeStatus.RECOMPUTED
    assert outcome.recomputed_event_id == recomputation_event_id(
        original.event_id, CHANGE_PROJECTION_ENGINE_VERSION
    )
    # (1) the original is untouched and still readable.
    assert await world.raw_payload(original.event_id) == before
    assert (await world.events.get(original.event_id, tenant_id)) is not None
    # (2) provenance: from which event, which engine, which evidence.
    recomputed = await world.events.get(outcome.recomputed_event_id, tenant_id)
    assert recomputed is not None and recomputed.event_type == "revision.recomputed"
    provenance = recomputed.payload["provenance"]
    assert provenance["recomputed_from_event_id"] == str(original.event_id)
    assert provenance["recomputed_from_engine"] == LEGACY
    assert provenance["diff_engine_version"] == CHANGE_PROJECTION_ENGINE_VERSION
    assert provenance["target_revision_id"] == str(v2.revision_id)
    assert recomputed.source_revision_id == v2.revision_id
    # The current matcher pairs the amended clause instead of removed + added.
    assert [c["change_type"] for c in recomputed.payload["changeset"]["changes"]] == ["modified"]
    # (3) the effective reader returns the recomputation; the legacy one is historical.
    effective = await world.events.get_change_for_revision(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id, revision_id=v2.revision_id
    )
    assert effective is not None and effective.event_id == recomputed.event_id
    history = await world.events.list_revision_outcomes(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id, revision_id=v2.revision_id
    )
    assert {e.event_id for e in history} == {original.event_id, recomputed.event_id}
    assert select_effective_outcome(history).superseded_by == {original.event_id: recomputed.event_id}
    assert qualify_event(original).legacy_matcher is True  # can never masquerade as current


async def test_recomputation_is_idempotent_for_reruns_and_duplicate_deliveries(db: AsyncSession) -> None:
    world = _World(db)
    tenant_id, project_id, _, _, original = await world.legacy_history()

    first = await recompute_legacy_changes_for_project(world.events, tenant_id=tenant_id, project_id=project_id)
    await db.commit()
    second = await recompute_legacy_changes_for_project(world.events, tenant_id=tenant_id, project_id=project_id)
    third = await recompute_legacy_change_event(world.events, original)
    await db.commit()

    assert [o.status for o in first] == [RecomputeStatus.RECOMPUTED]
    # The recomputed event is not itself eligible: only the original is offered again.
    assert [o.status for o in second] == [RecomputeStatus.ALREADY_RECOMPUTED]
    assert third.status is RecomputeStatus.ALREADY_RECOMPUTED
    assert await world.count_recomputed(tenant_id) == 1
    # A replay of the exact event is refused by the primary key, not by timestamps.
    recomputed = await world.events.get(first[0].recomputed_event_id, tenant_id)  # type: ignore[arg-type]
    assert recomputed is not None
    replay = recomputed.model_copy(update={"occurred_at": recomputed.occurred_at + timedelta(days=3)})
    assert await world.events.append_if_absent(replay) is False
    await db.commit()
    assert await world.count_recomputed(tenant_id) == 1


async def test_concurrent_recomputations_append_exactly_one_event(
    db: AsyncSession, independent_sessions: Any
) -> None:
    world = _World(db)
    tenant_id, project_id, _, _, _ = await world.legacy_history()

    results = await asyncio.gather(
        *(
            recompute_project_legacy_changes(
                tenant_id=tenant_id, project_id=project_id, session_factory=independent_sessions
            )
            for _ in range(4)
        )
    )
    assert sum(r["recomputed"] for r in results) == 1
    assert sum(r["already_recomputed"] for r in results) == 3
    assert await world.count_recomputed(tenant_id) == 1


async def test_recomputation_is_scoped_to_its_tenant_and_project(db: AsyncSession) -> None:
    world = _World(db)
    tenant_id, project_id, _, _, _ = await world.legacy_history()
    other_tenant, other_project, _ = await world.project()

    assert await recompute_legacy_changes_for_project(
        world.events, tenant_id=other_tenant, project_id=project_id
    ) == []
    assert await recompute_legacy_changes_for_project(
        world.events, tenant_id=tenant_id, project_id=other_project
    ) == []
    await db.commit()
    assert await world.count_recomputed(tenant_id) == 0
    assert await world.count_recomputed(other_tenant) == 0


async def test_missing_evidence_is_not_recomputable_and_nothing_is_written(db: AsyncSession) -> None:
    world = _World(db)
    tenant_id, project_id, document_id = await world.project()
    v1 = await world.revision(tenant_id, project_id, document_id, 1, None)
    v2 = await world.revision(tenant_id, project_id, document_id, 2, v1)
    # Only the target snapshot survives; the source evidence is gone.
    await world.events.append(world.snapshot(v2, V2_TEXT, minutes=21))
    original = await world.events.append(world.legacy_change(v1, v2, minutes=22))
    await db.commit()

    outcome = await recompute_legacy_change_event(world.events, original)
    await db.commit()
    assert outcome.status is RecomputeStatus.NOT_RECOMPUTABLE
    assert outcome.reason == "evidence_snapshot_missing"
    assert await world.count_recomputed(tenant_id) == 0
    # The legacy original stays the (LEGACY-qualified, needs-review) effective reading.
    effective = await world.events.get_change_for_revision(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id, revision_id=v2.revision_id
    )
    assert effective is not None and effective.event_id == original.event_id
    assert qualify_event(effective).effective_state == "needs_review"


async def test_current_matcher_comparisons_are_never_recomputed(db: AsyncSession) -> None:
    world = _World(db)
    tenant_id, project_id, document_id = await world.project()
    v1 = await world.revision(tenant_id, project_id, document_id, 1, None)
    v2 = await world.revision(tenant_id, project_id, document_id, 2, v1)
    s1 = world.snapshot(v1, V1_TEXT, minutes=11)
    s2 = world.snapshot(v2, V2_TEXT, minutes=21)
    await world.events.append(s1)
    await world.events.append(s2)
    changeset = diff_contract_revisions(
        project_id=project_id, tenant_id=tenant_id, from_revision_id=v1.revision_id,
        to_revision_id=v2.revision_id, old_clauses=[], new_clauses=[],
    )
    current = build_change_projection_event(
        changeset=changeset, document_id=document_id,
        source_blob_hash=v1.blob_hash, target_blob_hash=v2.blob_hash,
    )
    await world.events.append(current)
    await db.commit()

    assert await recompute_legacy_changes_for_project(
        world.events, tenant_id=tenant_id, project_id=project_id
    ) == []
    outcome = await recompute_legacy_change_event(world.events, current)
    assert outcome.status is RecomputeStatus.NOT_ELIGIBLE and outcome.reason == "matcher_current"
    assert await world.count_recomputed(tenant_id) == 0


async def test_a_newer_failed_analysis_leaves_no_current_comparison(db: AsyncSession) -> None:
    from src.temporal.application.change_projection import build_revision_processing_failed_event

    world = _World(db)
    tenant_id, project_id, document_id, v2, original = await world.legacy_history()
    failed = build_revision_processing_failed_event(revision=await _revision_of(db, v2.revision_id, tenant_id),
                                                    failure_code="parse_error")
    failed = failed.model_copy(update={"occurred_at": original.occurred_at + timedelta(minutes=5),
                                       "created_at": original.occurred_at + timedelta(minutes=5)})
    await world.events.append(failed)
    await db.commit()

    # Fail closed: the stale comparison is not served as the current one ...
    assert await world.events.get_change_for_revision(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id, revision_id=v2.revision_id
    ) is None
    # ... and it stays readable as history, superseded by the failure.
    history = await world.events.list_revision_outcomes(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id, revision_id=v2.revision_id
    )
    assert select_effective_outcome(history).superseded_by[original.event_id] == failed.event_id


async def _revision_of(db: AsyncSession, revision_id: UUID, tenant_id: UUID) -> DocumentRevision:
    revision = await SqlAlchemyDocumentRevisionRepository(db).get_by_id(revision_id, tenant_id)
    assert revision is not None
    return revision
