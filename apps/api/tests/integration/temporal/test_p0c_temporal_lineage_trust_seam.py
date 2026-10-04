"""PR-C2 lineage-aware temporal trust seam against PostgreSQL and the real #714 repository.

Refers to Suite ID: TS-INT-P0C-TEMPORAL-LINEAGE-001.

V1 TRUSTED -> V2 PROPOSED -> V3 (V2->V3 clean): V3 must not auto-promote while V2
is pending (M1) or after V2 is rejected (M2); an artifact of another document
bound to V2 does not make V2 trusted (M10); another tenant sees no trust (M9);
once V2's own candidate is approved through the canonical commit, V2 is the
new baseline and V3 follows the ordinary rule (M4/M12). A legacy unbound
TRUSTED artifact is never guessed as the baseline (M5).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import CandidateBinding, TrustState
from src.core.auth.models import SubscriptionPlan, Tenant, User
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Clause, ClauseType, DocumentType
from src.temporal.adapters import temporal_review_gate
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.revision_trust_reader import SqlAlchemyRevisionTrustReader
from src.temporal.application.revision_change_orchestrator import build_revision_analysis_events
from src.temporal.domain.document_revision import DocumentRevision

pytestmark = pytest.mark.asyncio

CLAUSE_TEXT = "The contractor pays a delay penalty of 1% per week."


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
            "created_at, updated_at) VALUES (:id, :tid, 'lineage', :code, 'construction', 'active', "
            "'EUR', now(), now())"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, user_id, project_id


async def _analyse(db: AsyncSession, revision: DocumentRevision) -> None:
    """The worker's revision-bound analysis events (identical clause -> clean comparison)."""
    clause = Clause(
        id=uuid4(),
        project_id=revision.project_id,
        tenant_id=revision.tenant_id,
        document_id=revision.document_id,
        clause_code="PEN-1",
        clause_type=ClauseType.PENALTY,
        title="Delay penalty",
        full_text=CLAUSE_TEXT,
    )
    events = SqlAlchemyProjectEventRepository(db)
    prior = await events.list_for_project(revision.project_id, revision.tenant_id)
    for event in await build_revision_analysis_events(
        revision=revision, clauses=[clause], existing_events=prior
    ):
        await events.append(event)
    await db.commit()


def _artifact(document_id: UUID, revision_id: UUID | None, title: str) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_id) if revision_id else None,
        doc_type="contract",
        extracted_risks=[RiskItem(title=title, description="d")],
    )


async def _latest_binding(db: AsyncSession, document_id: UUID) -> CandidateBinding:
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


async def test_untrusted_ancestor_blocks_until_a_new_trusted_baseline(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant, user, project = await _tenant_with_project(db)
    other_tenant, _u, _p = await _tenant_with_project(db)
    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    events = SqlAlchemyProjectEventRepository(db)
    artifacts = SqlAlchemyDocumentArtifactRepository(db)

    @asynccontextmanager
    async def _tenant_session(_tenant: UUID) -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(temporal_review_gate, "get_session_with_tenant", _tenant_session)

    async def gate(revision: DocumentRevision) -> tuple[bool, str]:
        decision = await temporal_review_gate.revision_requires_temporal_review(
            tenant_id=str(tenant),
            document_id=str(document.id),
            revision_id=str(revision.revision_id),
        )
        return decision.required, decision.reason

    async def reupload() -> DocumentRevision:
        await ReuploadDocumentUseCase(
            document_repository=doc_repo,
            revision_repository=rev_repo,
            storage_service=storage,
            event_repository=events,
        ).execute(
            tenant_id=tenant,
            document_id=document.id,
            file_content=f"%PDF penalty {uuid4()}".encode(),
            user_id=user,
        )
        return (await rev_repo.list_lineage(document.id, tenant))[-1]

    document = await UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=rev_repo,
        event_repository=events,
    ).execute(
        project_id=project,
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"%PDF penalty 1% per week")),
        document_type=DocumentType.CONTRACT,
        user_id=user,
        tenant_id=tenant,
    )
    [v1] = await rev_repo.list_lineage(document.id, tenant)
    await _analyse(db, v1)
    # V1: non-gated completion -> TRUSTED, bound to exactly V1.
    await artifacts.save(
        _artifact(document.id, v1.revision_id, "v1"), project_id=project, tenant_id=tenant
    )
    await db.commit()

    v2 = await reupload()
    await _analyse(db, v2)
    assert await gate(v2) == (False, "temporal_identity_resolved")  # anchored on trusted V1
    # V2: HITL-gated completion -> PROPOSED, awaiting review.
    await artifacts.save(
        _artifact(document.id, v2.revision_id, "v2"),
        project_id=project,
        tenant_id=tenant,
        trust_state=TrustState.PROPOSED,
    )
    await db.commit()

    v3 = await reupload()
    await _analyse(db, v3)

    # M1: V2 pending -> a clean V2->V3 diff cannot auto-trust V3.
    assert await gate(v3) == (True, "untrusted_ancestor_lineage")

    # M10: a TRUSTED artifact of ANOTHER document bound to V2 does not make V2 trusted.
    await artifacts.save(
        _artifact(uuid4(), v2.revision_id, "impostor"), project_id=project, tenant_id=tenant
    )
    await db.commit()
    assert await gate(v3) == (True, "untrusted_ancestor_lineage")

    # M9: another tenant cannot see (or lend) this document's trust.
    foreign = await SqlAlchemyRevisionTrustReader(db).read(
        tenant_id=other_tenant, document_id=document.id
    )
    assert foreign.states_by_revision == {} and foreign.unbound_trusted is False

    # M2: V2 rejected -> still not a baseline.
    assert await artifacts.reject_candidate(
        await _latest_binding(db, document.id), tenant_id=tenant
    )
    await db.commit()
    evidence = await SqlAlchemyRevisionTrustReader(db).read(
        tenant_id=tenant, document_id=document.id
    )
    assert evidence.states_by_revision[v2.revision_id] == frozenset({"rejected"})
    assert await gate(v3) == (True, "untrusted_ancestor_lineage")

    # M12/M4: V2 re-analysed and approved through the canonical commit -> new baseline.
    await artifacts.save(
        _artifact(document.id, v2.revision_id, "v2-reanalysed"),
        project_id=project,
        tenant_id=tenant,
        trust_state=TrustState.PROPOSED,
    )
    await db.commit()
    await artifacts.commit_candidate(await _latest_binding(db, document.id), tenant_id=tenant)
    await db.commit()
    assert await gate(v3) == (False, "temporal_identity_resolved")
    # Retry / resume re-evaluation gives the same answer (M11).
    assert await gate(v3) == (False, "temporal_identity_resolved")


async def test_legacy_unbound_trusted_artifact_is_never_guessed_as_baseline(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant, user, project = await _tenant_with_project(db)
    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    events = SqlAlchemyProjectEventRepository(db)

    @asynccontextmanager
    async def _tenant_session(_tenant: UUID) -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(temporal_review_gate, "get_session_with_tenant", _tenant_session)

    document = await UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=rev_repo,
        event_repository=events,
    ).execute(
        project_id=project,
        file=UploadFile(filename="legacy.pdf", file=BytesIO(b"%PDF legacy")),
        document_type=DocumentType.CONTRACT,
        user_id=user,
        tenant_id=tenant,
    )
    [v1] = await rev_repo.list_lineage(document.id, tenant)
    await _analyse(db, v1)
    # Pre-binding era: TRUSTED but with no revision binding.
    await SqlAlchemyDocumentArtifactRepository(db).save(
        _artifact(document.id, None, "legacy"), project_id=project, tenant_id=tenant
    )
    await db.commit()
    await ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
        event_repository=events,
    ).execute(
        tenant_id=tenant, document_id=document.id, file_content=b"%PDF legacy v2", user_id=user
    )
    v2 = (await rev_repo.list_lineage(document.id, tenant))[-1]
    await _analyse(db, v2)

    decision = await temporal_review_gate.revision_requires_temporal_review(
        tenant_id=str(tenant), document_id=str(document.id), revision_id=str(v2.revision_id)
    )

    assert decision.required is True
    assert decision.reason == "untrusted_ancestor_lineage"
    assert decision.detail == "legacy_unbound_baseline"
    # The first revision itself has no lineage to validate (M6).
    baseline = await temporal_review_gate.revision_requires_temporal_review(
        tenant_id=str(tenant), document_id=str(document.id), revision_id=str(v1.revision_id)
    )
    assert (baseline.required, baseline.reason) == (False, "baseline_revision")
