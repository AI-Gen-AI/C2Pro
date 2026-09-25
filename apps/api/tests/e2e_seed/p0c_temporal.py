"""Deterministic, repository-backed P0c PJ-01 temporal browser fixture.

The fixture is test infrastructure only.  It uses the canonical immutable
revision and ProjectEvent contracts so the browser reads exactly the temporal
projection that production reads; it never stubs the timeline HTTP response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_projection import (
    ChangeCause,
    build_change_projection_event,
)
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent
from tests.e2e_seed.seed_wedge import TENANT_ID, USER_ID, seed_e2e_auth_tenancy

_NAMESPACE = UUID("d7f75457-7ff8-4d6a-9cbb-badc0ffee001")
PROJECT_ID = uuid5(_NAMESPACE, "p0c-pj01-project")
DOCUMENT_ID = uuid5(_NAMESPACE, "p0c-pj01-contract")
_BASE = datetime(2026, 9, 14, 9, 0, tzinfo=UTC).replace(tzinfo=None)


def _id(name: str) -> UUID:
    return uuid5(_NAMESPACE, name)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class P0CBrowserFixture:
    """The immutable A/B/D revision lineage and visible B/C/D event stream."""

    project_id: UUID
    document_id: UUID
    baseline: DocumentRevision
    business_revision: DocumentRevision
    no_change_revision: DocumentRevision
    business_change: ProjectEvent
    newly_discovered: ProjectEvent
    no_change: ProjectEvent

    @property
    def timeline(self) -> list[ProjectEvent]:
        return [self.business_change, self.newly_discovered, self.no_change]


def _revision(name: str, rev_no: int, blob_text: str, parent: UUID | None, at: datetime) -> DocumentRevision:
    blob_hash = _hash(blob_text)
    return DocumentRevision(
        revision_id=_id(f"revision-{name}"),
        document_id=DOCUMENT_ID,
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        rev_no=rev_no,
        parent_revision_id=parent,
        blob_hash=blob_hash,
        blob_key=(
            f"tenants/{TENANT_ID}/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}/"
            f"revisions/{blob_hash}.txt"
        ),
        valid_from=at,
        created_at=at,
    )


def _event_at(event: ProjectEvent, at: datetime, event_id: UUID) -> ProjectEvent:
    return event.model_copy(update={"event_id": event_id, "occurred_at": at, "created_at": at})


def build_p0c_browser_fixture() -> P0CBrowserFixture:
    """Build the PJ-01 facts from canonical projection constructors.

    B changes the physical contract. C is a later L2 conclusion over B's
    preserved evidence, and D is a re-upload with no structural difference.
    """
    baseline = _revision("A", 1, "Completion is due on 30 June 2026.", None, _BASE)
    business_revision = _revision(
        "B", 2, "Completion is due on 31 July 2026.", baseline.revision_id, _BASE + timedelta(minutes=1)
    )
    no_change_revision = _revision(
        "D", 3, "Completion is due on 31 July 2026.", business_revision.revision_id, _BASE + timedelta(minutes=2)
    )
    evidence = EvidenceRef(
        ref_id="pj01-contract-completion",
        source="PJ-01 Contract",
        tier=EvidenceTier.VERIFIED,
        locator="Clause 4.2",
    )
    business_changeset = ChangeSet(
        changeset_id=_id("changeset-B"),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        from_revision_id=baseline.revision_id,
        to_revision_id=business_revision.revision_id,
        changes=[
            SemanticChange(
                object_type="clause",
                change_type="modified",
                anchor="Clause 4.2",
                before={"full_text": "Completion is due on 30 June 2026."},
                after={"full_text": "Completion is due on 31 July 2026."},
                semantic_summary="The contractual completion date moved by one month.",
                match_confidence=1.0,
                confidence=0.94,
                evidence_refs=[evidence],
            )
        ],
        created_at=_BASE + timedelta(minutes=1),
    )
    business = _event_at(
        build_change_projection_event(
            changeset=business_changeset,
            document_id=DOCUMENT_ID,
            source_blob_hash=baseline.blob_hash,
            target_blob_hash=business_revision.blob_hash,
            semantic_provider="deterministic-test-provider",
            semantic_model="pj01-l2",
            semantic_model_version="pj01-l2-2026-09",
        ),
        _BASE + timedelta(minutes=3),
        _id("event-B-business-change"),
    )
    discovered_changeset = business_changeset.model_copy(
        update={
            "changeset_id": _id("changeset-C-reinterpretation"),
            "changes": [
                business_changeset.changes[0].model_copy(
                    update={
                        "semantic_summary": (
                            "The later interpretation identifies the one-month shift as a newly "
                            "discovered delivery-obligation exposure."
                        ),
                        "severity": "high",
                        "confidence": 0.91,
                    }
                )
            ],
        }
    )
    discovered = _event_at(
        build_change_projection_event(
            changeset=discovered_changeset,
            document_id=DOCUMENT_ID,
            source_blob_hash=baseline.blob_hash,
            target_blob_hash=business_revision.blob_hash,
            semantic_provider="deterministic-test-provider",
            semantic_model="pj01-l2",
            semantic_model_version="pj01-l2-2026-09",
            change_cause=ChangeCause.NEWLY_DISCOVERED,
            event_type="revision.reinterpreted",
            provenance_extra={"reinterpretation_of_event_id": str(business.event_id)},
        ),
        _BASE + timedelta(minutes=4),
        _id("event-C-newly-discovered"),
    )
    no_change_changeset = ChangeSet(
        changeset_id=_id("changeset-D-no-change"),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        from_revision_id=business_revision.revision_id,
        to_revision_id=no_change_revision.revision_id,
        changes=[],
        created_at=_BASE + timedelta(minutes=2),
    )
    no_change = _event_at(
        build_change_projection_event(
            changeset=no_change_changeset,
            document_id=DOCUMENT_ID,
            source_blob_hash=business_revision.blob_hash,
            target_blob_hash=no_change_revision.blob_hash,
        ),
        _BASE + timedelta(minutes=5),
        _id("event-D-no-change"),
    )
    return P0CBrowserFixture(
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        baseline=baseline,
        business_revision=business_revision,
        no_change_revision=no_change_revision,
        business_change=business,
        newly_discovered=discovered,
        no_change=no_change,
    )


async def seed_p0c_browser_fixture(db: AsyncSession) -> dict[str, object]:
    """Persist the PJ-01 fixture idempotently through P0c repositories."""
    fixture = build_p0c_browser_fixture()
    await seed_e2e_auth_tenancy(db)
    if await db.get(ProjectORM, fixture.project_id) is None:
        db.add(ProjectORM(
            id=fixture.project_id, tenant_id=TENANT_ID, name="PJ-01 What Changed",
            code="PJ-01-P0C", project_type="construction", status="active", currency="EUR",
        ))
        await db.flush()
    if await db.get(DocumentORM, fixture.document_id) is None:
        db.add(DocumentORM(
            id=fixture.document_id, tenant_id=TENANT_ID, project_id=fixture.project_id,
            document_type=DocumentType.CONTRACT, filename="pj01-contract.txt",
            upload_status=DocumentStatus.ANALYZED, storage_url=fixture.no_change_revision.blob_key,
            file_size_bytes=45, file_hash=fixture.no_change_revision.blob_hash, created_by=USER_ID,
        ))
        await db.flush()
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    for revision in (fixture.baseline, fixture.business_revision, fixture.no_change_revision):
        if await revisions.get_by_id(revision.revision_id, TENANT_ID) is None:
            if revision.rev_no > 1:
                await revisions.close_current(fixture.document_id, TENANT_ID, revision.valid_from)
            await revisions.append_revision(revision)
    events = SqlAlchemyProjectEventRepository(db)
    for event in fixture.timeline:
        if await events.get(event.event_id, TENANT_ID) is None:
            await events.append(event)
    await db.commit()
    return {
        "project_id": str(fixture.project_id), "document_id": str(fixture.document_id),
        "revisions": {
            "A": {"revision_id": str(fixture.baseline.revision_id), "blob_hash": fixture.baseline.blob_hash},
            "B": {"revision_id": str(fixture.business_revision.revision_id), "blob_hash": fixture.business_revision.blob_hash},
            "D": {"revision_id": str(fixture.no_change_revision.revision_id), "blob_hash": fixture.no_change_revision.blob_hash},
        },
        "events": {
            "B": {"event_id": str(fixture.business_change.event_id), "change_cause": "BUSINESS_STATE_CHANGED"},
            "C": {"event_id": str(fixture.newly_discovered.event_id), "change_cause": "NEWLY_DISCOVERED"},
            "D": {"event_id": str(fixture.no_change.event_id), "change_cause": None},
        },
    }


__all__ = ["P0CBrowserFixture", "build_p0c_browser_fixture", "seed_p0c_browser_fixture"]
