"""C3a revision-correct clause truth against PostgreSQL (TS-INT-C3A-REVISION-CLAUSES-001).

V1 and V2 of one contract both persist their own clause rows, physically bound to
their revision. "Current" is answered by ONE trusted-current resolver whose only
authority is the #714 TRUSTED artifact bound to a revision -- never the latest
upload, the latest analysis or the highest rev_no:

* V1 TRUSTED + V2 PROPOSED -> every current reader (document detail, relationship
  explanation, SourceLocator, /coherence/evaluate clauses, the budget builder's
  contract total, RAG chunks) reads V1, and never a mix of V1 and V2;
* V2 REJECTED -> V1 stays current, V2 stays immutable history;
* V2 approved through the canonical #714 commit -> current switches to V2, and V1's
  rows are left exactly as they were (no copy, no delete);
* an explicit historical read returns the requested revision without moving current.

The analysis loader reads the processing-authority-pinned revision; ambiguous
legacy identity fails closed; tenants and documents are isolated.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import CandidateBinding, TrustState
from src.core.auth.models import SubscriptionPlan, Tenant, User
from src.documents.adapters.persistence.models import ClauseORM
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.get_document_with_clauses_use_case import (
    GetDocumentWithClausesUseCase,
)
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.revision_clauses import persist_revision_clauses
from src.documents.application.services.source_locator import SourceLocator
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Clause, ClauseType, Document, DocumentType
from src.temporal.adapters.persistence.current_revision_resolver import (
    SqlAlchemyCurrentRevisionResolver,
)
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.current_revision import CurrentRevisionStatus
from src.temporal.domain.document_revision import DocumentRevision

pytestmark = pytest.mark.asyncio

V1_TEXT = "Clause 14.2 The contractor pays a delay penalty of 1% per week of delay."
V2_TEXT = "Clause 14.2 The contractor pays a delay penalty of 5% per week of delay."


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("upload_document_use_case", "reupload_document_use_case"):
        monkeypatch.setattr(
            f"src.documents.application.{module}.enqueue_project_snapshot", lambda **_kwargs: None
        )
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case._enqueue_document_processing",
        lambda _document_id, _revision_id=None, _generation=None: None,
    )


async def _tenant_with_project(db: AsyncSession) -> tuple[UUID, UUID, UUID]:
    tenant_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    db.add_all(
        [
            Tenant(
                id=tenant_id,
                name="t",
                slug=f"t-{tenant_id.hex[:8]}",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                ai_budget_monthly=100.0,
            ),
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"u-{user_id.hex[:8]}@test.com",
                hashed_password="h",
                first_name="t",
                last_name="t",
                role="admin",
            ),
        ]
    )
    await db.commit()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
            "created_at, updated_at) VALUES (:id, :tid, 'c3a', :code, 'construction', 'active', "
            "'EUR', now(), now())"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, user_id, project_id


class _World:
    """One tenant's project with a contract and helpers to revise / trust it."""

    def __init__(self, db: AsyncSession, tmp_path: Path) -> None:
        self.db = db
        self.storage = LocalFileStorageService(base_dir=tmp_path)
        self.docs = SqlAlchemyDocumentRepository(db)
        self.revisions = SqlAlchemyDocumentRevisionRepository(db)
        self.events = SqlAlchemyProjectEventRepository(db)
        self.artifacts = SqlAlchemyDocumentArtifactRepository(db)
        self.tenant: UUID
        self.user: UUID
        self.project: UUID

    async def setup(self) -> _World:
        self.tenant, self.user, self.project = await _tenant_with_project(self.db)
        return self

    async def upload(self, name: str = "contract.pdf") -> Document:
        return await UploadDocumentUseCase(
            document_repository=self.docs,
            storage_service=self.storage,
            project_repository=_ProjectRepo(),  # type: ignore[arg-type]
            revision_repository=self.revisions,
            event_repository=self.events,
        ).execute(
            project_id=self.project,
            file=UploadFile(filename=name, file=BytesIO(f"%PDF {uuid4()}".encode())),
            document_type=DocumentType.CONTRACT,
            user_id=self.user,
            tenant_id=self.tenant,
        )

    async def reupload(self, document: Document) -> DocumentRevision:
        await ReuploadDocumentUseCase(
            document_repository=self.docs,
            revision_repository=self.revisions,
            storage_service=self.storage,
            event_repository=self.events,
        ).execute(
            tenant_id=self.tenant,
            document_id=document.id,
            file_content=f"%PDF {uuid4()}".encode(),
            user_id=self.user,
        )
        return (await self.revisions.list_lineage(document.id, self.tenant))[-1]

    async def lineage(self, document: Document) -> list[DocumentRevision]:
        return await self.revisions.list_lineage(document.id, self.tenant)

    def clause(
        self,
        document: Document,
        full_text: str,
        *,
        code: str = "AUTO-001",
        entities: dict[str, Any] | None = None,
    ) -> Clause:
        return Clause(
            id=uuid4(),
            project_id=self.project,
            tenant_id=self.tenant,
            document_id=document.id,
            clause_code=code,
            clause_type=ClauseType.PENALTY,
            title=full_text[:40],
            full_text=full_text,
            extracted_entities=dict(entities or {}),
        )

    async def persist(
        self, document: Document, revision: DocumentRevision, *clauses: Clause
    ) -> list[Clause]:
        result = await persist_revision_clauses(
            self.docs,
            tenant_id=self.tenant,
            document_id=document.id,
            revision_id=revision.revision_id,
            extracted=list(clauses),
        )
        await self.db.commit()
        return list(result.clauses)

    async def trust(self, document: Document, revision: DocumentRevision) -> None:
        """Non-gated completion: the artifact is TRUSTED, bound to exactly ``revision``."""
        await self.artifacts.save(
            _artifact(document.id, revision.revision_id), project_id=self.project, tenant_id=self.tenant
        )
        await self.db.commit()

    async def propose(self, document: Document, revision: DocumentRevision) -> CandidateBinding:
        """HITL-gated completion: the artifact is PROPOSED, awaiting review."""
        await self.artifacts.save(
            _artifact(document.id, revision.revision_id),
            project_id=self.project,
            tenant_id=self.tenant,
            trust_state=TrustState.PROPOSED,
        )
        await self.db.commit()
        return await _latest_proposed(self.db, document.id)

    async def current(self, document: Document) -> Any:
        return await SqlAlchemyCurrentRevisionResolver(self.db).resolve(
            tenant_id=self.tenant, document_id=document.id
        )

    async def current_texts(self, document: Document) -> set[str | None]:
        return {c.full_text for c in await self.docs.list_current_clauses(self.tenant, document.id)}


def _artifact(document_id: UUID, revision_id: UUID | None) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_id) if revision_id else None,
        doc_type="contract",
        extracted_risks=[RiskItem(title="penalty", description="d")],
    )


async def _latest_proposed(db: AsyncSession, document_id: UUID) -> CandidateBinding:
    row = (
        (
            await db.execute(
                select(DocumentArtifactORM)
                .where(
                    DocumentArtifactORM.document_id == document_id,
                    DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
                )
                .order_by(DocumentArtifactORM.artifact_version.desc())
            )
        )
        .scalars()
        .first()
    )
    assert row is not None
    return CandidateBinding(
        row.artifact_id, row.document_id, int(row.artifact_version), str(row.artifact_hash)
    )


async def _v1_trusted_v2_proposed(
    world: _World,
) -> tuple[Document, DocumentRevision, DocumentRevision, list[Clause], list[Clause], CandidateBinding]:
    document = await world.upload()
    [v1] = await world.lineage(document)
    # The SAME clause code in both revisions: only the revision tells them apart.
    v1_rows = await world.persist(document, v1, world.clause(document, V1_TEXT, code="14.2"))
    await world.trust(document, v1)
    v2 = await world.reupload(document)
    v2_rows = await world.persist(document, v2, world.clause(document, V2_TEXT, code="14.2"))
    binding = await world.propose(document, v2)
    return document, v1, v2, v1_rows, v2_rows, binding


# ── 1, 2, 7, 9, 10, 11, 23, 24 ──────────────────────────────────────────────


async def test_v1_and_v2_coexist_and_current_follows_only_the_trusted_artifact(
    db: AsyncSession, tmp_path: Path
) -> None:
    world = await _World(db, tmp_path).setup()
    document, v1, v2, v1_rows, v2_rows, binding = await _v1_trusted_v2_proposed(world)

    # (1) both revisions' rows coexist; (2) each new row carries its exact revision.
    rows = (
        await db.execute(select(ClauseORM).where(ClauseORM.document_id == document.id))
    ).scalars().all()
    assert {(row.full_text, row.revision_id) for row in rows} == {
        (V1_TEXT, v1.revision_id),
        (V2_TEXT, v2.revision_id),
    }
    assert [c.revision_id for c in v1_rows] == [v1.revision_id]
    assert [c.revision_id for c in v2_rows] == [v2.revision_id]

    # (7) V2 is the latest upload AND the latest analysis, yet PROPOSED: not current.
    current = await world.current(document)
    assert (current.status, current.revision_id) == (CurrentRevisionStatus.TRUSTED, v1.revision_id)
    assert await world.current_texts(document) == {V1_TEXT}

    # (11) the document detail reads one set, never a V1+V2 mix.
    detail = await GetDocumentWithClausesUseCase(world.docs).execute(world.tenant, document.id)
    assert [c.full_text for c in detail.clauses] == [V1_TEXT]
    assert {c.revision_id for c in detail.clauses} == {v1.revision_id}

    # (10) the same clause code exists in V1 and V2: SourceLocator resolves the current one.
    locator = SourceLocator(world.docs)
    fast = await locator.locate_evidence("see Clause 14.2", document.id, world.tenant)
    assert fast is not None and fast.chunk_text == V1_TEXT
    by_code = await world.docs.get_clause_by_document_and_code(world.tenant, document.id, "14.2")
    assert by_code is not None and by_code.id == v1_rows[0].id
    slow = await locator.locate_evidence("delay penalty of 5% per week", document.id, world.tenant)
    assert slow is None or slow.chunk_text == V1_TEXT
    # ... and an explicit historical locate reads V2 only.
    historical = await locator.locate_evidence(
        "delay penalty of 5% per week", document.id, world.tenant, revision_id=v2.revision_id
    )
    assert historical is not None and historical.chunk_text == V2_TEXT

    # (24) an explicit historical read returns V2 without changing current truth.
    v2_detail = await GetDocumentWithClausesUseCase(world.docs).execute(
        world.tenant, document.id, revision_id=v2.revision_id
    )
    assert [c.full_text for c in v2_detail.clauses] == [V2_TEXT]
    assert (await world.current(document)).revision_id == v1.revision_id
    assert await world.current_texts(document) == {V1_TEXT}

    # (9) V2 approved through the canonical #714 commit -> current switches to V2.
    await world.artifacts.commit_candidate(binding, tenant_id=world.tenant)
    await db.commit()
    current = await world.current(document)
    assert (current.status, current.revision_id) == (CurrentRevisionStatus.TRUSTED, v2.revision_id)
    assert await world.current_texts(document) == {V2_TEXT}

    # (23) V1's rows are untouched: same ids, same text, same binding, nothing copied.
    after = {
        row.id: (row.full_text, row.revision_id)
        for row in (
            await db.execute(select(ClauseORM).where(ClauseORM.document_id == document.id))
        ).scalars()
    }
    assert after == {
        v1_rows[0].id: (V1_TEXT, v1.revision_id),
        v2_rows[0].id: (V2_TEXT, v2.revision_id),
    }
    historical_v1 = await world.docs.list_revision_clauses(world.tenant, document.id, v1.revision_id)
    assert [c.id for c in historical_v1] == [v1_rows[0].id]


# ── 8 ───────────────────────────────────────────────────────────────────────


async def test_rejected_v2_is_never_current_and_remains_history(
    db: AsyncSession, tmp_path: Path
) -> None:
    world = await _World(db, tmp_path).setup()
    document, v1, v2, _v1_rows, v2_rows, binding = await _v1_trusted_v2_proposed(world)

    assert await world.artifacts.reject_candidate(binding, tenant_id=world.tenant)
    await db.commit()

    current = await world.current(document)
    assert (current.status, current.revision_id) == (CurrentRevisionStatus.TRUSTED, v1.revision_id)
    assert await world.current_texts(document) == {V1_TEXT}
    history = await world.docs.list_revision_clauses(world.tenant, document.id, v2.revision_id)
    assert [c.id for c in history] == [v2_rows[0].id]


# ── 3 ───────────────────────────────────────────────────────────────────────


async def test_database_rejects_a_clause_bound_to_another_documents_revision(
    db: AsyncSession, tmp_path: Path
) -> None:
    world = await _World(db, tmp_path).setup()
    document = await world.upload("a.pdf")
    other = await world.upload("b.pdf")
    [other_v1] = await world.lineage(other)

    db.add(
        ClauseORM(
            id=uuid4(),
            tenant_id=world.tenant,
            project_id=world.project,
            document_id=document.id,
            clause_code="AUTO-001",
            full_text="x",
            revision_id=other_v1.revision_id,
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


# ── 4, 5 (ingestion staging, real events) ───────────────────────────────────


async def test_ingestion_staging_is_idempotent_and_snapshot_ids_are_persisted_ids(
    db: AsyncSession, tmp_path: Path
) -> None:
    from src.core.tasks import ingestion_tasks

    world = await _World(db, tmp_path).setup()
    document = await world.upload()
    [v1] = await world.lineage(document)
    parsed_text = (
        "1.- Penalties. The contractor pays a delay penalty of 1% per week of delay.\n\n"
        "2.- Payment. The owner pays each certified invoice within thirty days of receipt."
    )

    async def stage() -> int:
        inserted = await ingestion_tasks._stage_contract_clauses(
            db,
            world.docs,
            document=document,
            tenant_id=world.tenant,
            source_revision=v1,
            authority_revision_id=v1.revision_id,
            parsed_text=parsed_text,
            parsed_payload={},
        )
        await db.commit()
        return inserted

    assert await stage() == 2
    first = await world.docs.list_revision_clauses(world.tenant, document.id, v1.revision_id)
    # (4) a retry / replay of the same pinned revision adds nothing and keeps identity.
    assert await stage() == 0
    again = await world.docs.list_revision_clauses(world.tenant, document.id, v1.revision_id)
    assert sorted(c.id for c in again) == sorted(c.id for c in first)
    assert len(again) == 2

    # (5) the immutable snapshot's clause entity ids ARE the persisted row ids.
    events = await world.events.list_for_revision(tenant_id=world.tenant, revision_id=v1.revision_id)
    [snapshot] = [e for e in events if e.event_type == "revision.analyzed"]
    assert sorted(UUID(c["id"]) for c in snapshot.payload["clauses"]) == sorted(c.id for c in first)

    # A stage whose authority pinned another revision writes nothing (fail closed).
    with pytest.raises(ValueError):
        await ingestion_tasks._stage_contract_clauses(
            db,
            world.docs,
            document=document,
            tenant_id=world.tenant,
            source_revision=v1,
            authority_revision_id=uuid4(),
            parsed_text=parsed_text,
            parsed_payload={},
        )
    await db.rollback()


async def test_reprocessing_a_legacy_revision_reuses_its_snapshot_identity(
    db: AsyncSession, tmp_path: Path
) -> None:
    """A pre-C3a V2 has a snapshot but no rows: its rows take the snapshot's ids."""
    from src.core.tasks import ingestion_tasks
    from src.temporal.application.revision_change_orchestrator import (
        build_revision_analysis_events,
    )

    world = await _World(db, tmp_path).setup()
    document = await world.upload()
    [v1] = await world.lineage(document)
    legacy = world.clause(document, "1.- Penalties. The contractor pays a delay penalty of 1% per week.")
    for event in await build_revision_analysis_events(
        revision=v1, clauses=[legacy], existing_events=[]
    ):
        await world.events.append(event)
    await db.commit()

    inserted = await ingestion_tasks._stage_contract_clauses(
        db,
        world.docs,
        document=document,
        tenant_id=world.tenant,
        source_revision=v1,
        authority_revision_id=v1.revision_id,
        parsed_text="1.- Penalties. The contractor pays a delay penalty of 1% per week.",
        parsed_payload={},
    )
    await db.commit()
    assert inserted == 1
    [row] = await world.docs.list_revision_clauses(world.tenant, document.id, v1.revision_id)
    assert row.id == legacy.id


# ── 6 ───────────────────────────────────────────────────────────────────────


async def test_analysis_loader_reads_exactly_the_pinned_revision(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.analysis.adapters.graph.clause_evidence_loader import load_persisted_clause_evidence

    @asynccontextmanager
    async def _tenant_session(_tenant: UUID) -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr("src.core.database.get_session_with_tenant", _tenant_session)
    world = await _World(db, tmp_path).setup()
    document, v1, v2, v1_rows, v2_rows, _binding = await _v1_trusted_v2_proposed(world)

    pinned_v2 = await load_persisted_clause_evidence(
        world.tenant, document.id, revision_id=v2.revision_id
    )
    assert [c.id for c in pinned_v2] == [v2_rows[0].id]
    pinned_v1 = await load_persisted_clause_evidence(
        world.tenant, document.id, revision_id=v1.revision_id
    )
    assert [c.id for c in pinned_v1] == [v1_rows[0].id]


# ── 12, 13 ──────────────────────────────────────────────────────────────────


async def test_evaluate_clauses_and_budget_contract_total_ignore_proposed_v2(
    db: AsyncSession, tmp_path: Path
) -> None:
    from src.coherence.budget_clause_builder import load_contract_total
    from src.coherence.router import get_clauses_from_rag

    world = await _World(db, tmp_path).setup()
    document = await world.upload()
    [v1] = await world.lineage(document)
    v1_rows = await world.persist(
        document, v1, world.clause(document, V1_TEXT, entities={"total_amount": 1000})
    )
    await world.trust(document, v1)
    v2 = await world.reupload(document)
    await world.persist(
        document, v2, world.clause(document, V2_TEXT, entities={"total_amount": 5000})
    )
    await world.propose(document, v2)

    clauses = await get_clauses_from_rag(db, world.project, world.tenant)
    persisted = [c for c in clauses if c.data.get("source") == "persisted_clause"]
    assert [c.id for c in persisted] == [str(v1_rows[0].id)]
    assert await load_contract_total(db, world.project, world.tenant) == 1000.0


# ── 14 ──────────────────────────────────────────────────────────────────────


async def test_ambiguous_legacy_identity_fails_closed(db: AsyncSession, tmp_path: Path) -> None:
    from src.coherence.router import get_clauses_from_rag

    world = await _World(db, tmp_path).setup()
    document = await world.upload()
    [v1] = await world.lineage(document)
    # Legacy: unbound clause rows and an unbound (pre-binding) TRUSTED artifact.
    world.docs.session.add(
        ClauseORM(
            id=uuid4(),
            tenant_id=world.tenant,
            project_id=world.project,
            document_id=document.id,
            clause_code="AUTO-001",
            full_text=V1_TEXT,
        )
    )
    await world.artifacts.save(
        _artifact(document.id, None), project_id=world.project, tenant_id=world.tenant
    )
    await db.commit()

    # Exactly one revision: the single baseline clause set is unambiguous.
    single = await world.current(document)
    assert single.status is CurrentRevisionStatus.SINGLE_REVISION
    assert await world.current_texts(document) == {V1_TEXT}

    # A second revision with no bound TRUSTED artifact: which one is trusted is unknown.
    v2 = await world.reupload(document)
    await world.persist(document, v2, world.clause(document, V2_TEXT))
    ambiguous = await world.current(document)
    assert (ambiguous.status, ambiguous.revision_id) == (CurrentRevisionStatus.UNRESOLVED, None)
    assert await world.current_texts(document) == set()
    detail = await GetDocumentWithClausesUseCase(world.docs).execute(world.tenant, document.id)
    assert detail.clauses == []
    assert [
        c for c in await get_clauses_from_rag(db, world.project, world.tenant)
        if c.data.get("document_id") == str(document.id)
    ] == []
    # History is still addressable explicitly.
    assert [
        c.full_text
        for c in await world.docs.list_revision_clauses(world.tenant, document.id, v2.revision_id)
    ] == [V2_TEXT]
    assert v1.revision_id != v2.revision_id


# ── 15, 16 ──────────────────────────────────────────────────────────────────


async def test_tenant_and_document_isolation(db: AsyncSession, tmp_path: Path) -> None:
    world = await _World(db, tmp_path).setup()
    other_world = await _World(db, tmp_path).setup()
    document, v1, v2, v1_rows, _v2_rows, _binding = await _v1_trusted_v2_proposed(world)
    sibling = await world.upload("sibling.pdf")
    [s1] = await world.lineage(sibling)
    await world.persist(sibling, s1, world.clause(sibling, "Sibling clause text about payment terms."))

    # (16) a TRUSTED artifact of ANOTHER document bound to V2 does not make V2 current.
    await world.artifacts.save(
        _artifact(sibling.id, v2.revision_id), project_id=world.project, tenant_id=world.tenant
    )
    await db.commit()
    assert (await world.current(document)).revision_id == v1.revision_id
    assert [c.id for c in await world.docs.list_current_clauses(world.tenant, document.id)] == [
        v1_rows[0].id
    ]
    # An explicit historical read of another document's revision returns nothing.
    assert await world.docs.list_revision_clauses(world.tenant, sibling.id, v1.revision_id) == []

    # (15) another tenant resolves nothing and reads nothing for this document.
    foreign = await SqlAlchemyCurrentRevisionResolver(db).resolve(
        tenant_id=other_world.tenant, document_id=document.id
    )
    assert foreign.revision_id is None
    assert await world.docs.list_current_clauses(other_world.tenant, document.id) == []
    assert (
        await world.docs.list_revision_clauses(other_world.tenant, document.id, v1.revision_id) == []
    )
    assert (
        await world.docs.get_document_with_clauses(other_world.tenant, document.id) is None
    )


# ── 19 ──────────────────────────────────────────────────────────────────────


async def test_rag_chunks_of_a_proposed_revision_are_excluded(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.analysis.adapters.http.router import get_document_text_from_rag
    from src.coherence.router import _get_rag_chunk_clauses
    from src.documents.adapters.rag import rag_service

    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.001] * rag_service.EMBEDDING_DIMENSION for _ in texts]

    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    world = await _World(db, tmp_path).setup()
    document = await world.upload()
    [v1] = await world.lineage(document)
    await world.trust(document, v1)

    async def ingest(revision: DocumentRevision, body: str) -> None:
        await rag_service.RagService(db).ingest_document(
            tenant_id=world.tenant,
            document_id=document.id,
            project_id=world.project,
            text_content=body,
            metadata={"document_type": "contract", "revision_id": str(revision.revision_id)},
        )

    await ingest(v1, "V1 chunk: penalty one percent per week.")
    v2 = await world.reupload(document)
    await ingest(v2, "V2 chunk: penalty five percent per week.")
    await world.propose(document, v2)

    coherence_chunks = await _get_rag_chunk_clauses(db, world.project, world.tenant, 50)
    assert [c.text for c in coherence_chunks] == ["V1 chunk: penalty one percent per week."]
    retrieved = await rag_service._retrieve_chunks(
        db, tenant_id=world.tenant, project_id=world.project, embedding=[0.001] * 1536, top_k=10
    )
    assert [c.content for c in retrieved] == ["V1 chunk: penalty one percent per week."]
    _text, chunks = await get_document_text_from_rag(
        db, world.project, world.tenant, document_id=document.id
    )
    assert [c["content"] for c in chunks] == ["V1 chunk: penalty one percent per week."]

    # Unstamped (pre-C3a) chunks of a multi-revision document are ambiguous: excluded.
    await db.execute(
        text(
            "UPDATE document_chunks SET metadata = metadata - 'revision_id' "
            "WHERE document_id = :d"
        ),
        {"d": document.id},
    )
    await db.commit()
    assert await _get_rag_chunk_clauses(db, world.project, world.tenant, 50) == []


async def test_rag_readiness_never_borrows_another_revisions_chunks(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A V2 whose embedding failed is not RAG-ready because V1's chunks were retained."""
    from src.core.tasks.ingestion_tasks import get_document_rag_chunk_count
    from src.documents.adapters.rag import rag_service

    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.001] * rag_service.EMBEDDING_DIMENSION for _ in texts]

    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    world = await _World(db, tmp_path).setup()
    document = await world.upload()
    [v1] = await world.lineage(document)

    async def count(revision: DocumentRevision) -> int:
        return await get_document_rag_chunk_count(
            session=db, tenant_id=world.tenant, document_id=document.id,
            revision_id=revision.revision_id,
        )

    # Pre-C3a (unstamped) chunks of a single-revision document are that revision's.
    await rag_service.RagService(db).ingest_document(
        tenant_id=world.tenant, document_id=document.id, project_id=world.project,
        text_content="legacy chunk", metadata={"document_type": "contract"},
    )
    assert await count(v1) == 1

    await rag_service.RagService(db).ingest_document(
        tenant_id=world.tenant, document_id=document.id, project_id=world.project,
        text_content="V1 chunk", metadata={"document_type": "contract", "revision_id": str(v1.revision_id)},
    )
    v2 = await world.reupload(document)
    # V2's embedding "failed": nothing stamped V2 exists, V1's chunks are retained.
    assert await count(v1) == 1
    assert await count(v2) == 0
