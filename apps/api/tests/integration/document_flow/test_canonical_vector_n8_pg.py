"""Single PostgreSQL proof: canonical vector writer → pgvector pairs for N8.

Synthetic contract and technical requirement; no provider calls or real data.
"""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.coherence.adapters.persistence.pgvector_embedding_repository import (
    PgvectorEmbeddingRepository,
)
from src.coherence.application.canonical_clause_vectors import index_current_clause_vectors
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentType
from tests.modules.integration.test_c3a_revision_bound_clauses import (
    _ProjectRepo,
    _World,
)

pytestmark = pytest.mark.asyncio


async def test_real_pg_source_clause_vectors_feed_n8_without_untrusted_revisions(
    db: AsyncSession, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case._enqueue_document_processing",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        lambda **_kwargs: None,
    )
    world = await _World(db, tmp_path).setup()

    contract = await world.upload("contract.pdf")
    [contract_rev] = await world.lineage(contract)
    [contract_clause] = await world.persist(
        contract, contract_rev,
        world.clause(
            contract, "Supplier shall supply all EPC transformers before handover."
        ),
    )
    await world.trust(contract, contract_rev)

    specification = await UploadDocumentUseCase(
        document_repository=world.docs,
        storage_service=world.storage,
        project_repository=_ProjectRepo(),
        revision_repository=world.revisions,
        event_repository=world.events,
    ).execute(
        project_id=world.project,
        file=UploadFile(filename="spec.pdf", file=BytesIO(b"%PDF synthetic requirement")),
        document_type=DocumentType.TECHNICAL_SPEC,
        user_id=world.user,
        tenant_id=world.tenant,
    )
    [spec_rev] = await world.lineage(specification)
    [spec_clause] = await world.persist(
        specification, spec_rev,
        world.clause(
            specification, "Supplier must deliver all EPC transformers by handover."
        ),
    )
    await world.artifacts.save(
        DocumentArtifact(
            document_id=str(specification.id),
            document_revision_id=str(spec_rev.revision_id),
            doc_type="technical_spec",
            extracted_risks=[RiskItem(title="requirement", description="synthetic")],
        ),
        project_id=world.project,
        tenant_id=world.tenant,
    )
    await db.commit()

    requested = [str(contract_clause.id), str(spec_clause.id)]

    async def fake_embeddings(texts: list[str]) -> list[list[float]]:
        assert len(texts) == 2
        return [[0.125] * 1536 for _ in texts]

    result = await index_current_clause_vectors(
        db=db, tenant_id=world.tenant, project_id=world.project,
        clause_ids=requested, embed=fake_embeddings,
    )
    assert result["indexed"] == 2
    await db.commit()

    indexed = (await db.execute(
        text("""
            SELECT clause_id, metadata->>'revision_id' AS revision_id,
                   metadata->>'embedding_model' AS model
            FROM public.clause_embeddings
            WHERE project_id = CAST(:project_id AS uuid)
              AND tenant_id = CAST(:tenant_id AS uuid)
        """),
        {"project_id": str(world.project), "tenant_id": str(world.tenant)},
    )).all()
    assert len(indexed) == 2
    assert {row[0] for row in indexed} == set(requested)
    assert {row[1] for row in indexed} == {
        str(contract_rev.revision_id), str(spec_rev.revision_id)
    }
    assert {row[2] for row in indexed} == {"text-embedding-3-small"}

    repo = PgvectorEmbeddingRepository(db, tenant_id=world.tenant)
    pairs = await repo.find_cross_document_pairs(
        project_id=world.project, similarity_threshold=0.9, max_pairs=10,
    )
    assert len(pairs) == 1
    assert {pairs[0].source_clause_id, pairs[0].target_clause_id} == set(requested)
    assert pairs[0].similarity_score > 0.999

    # Propose V2 of the contract without approval: it MUST NOT become an
    # eligible source nor change the existing canonical cross-document pair.
    v2 = await world.reupload(contract)
    [v2_clause] = await world.persist(
        contract, v2,
        world.clause(contract, "Supplier may omit all transformers."),
    )
    await world.propose(contract, v2)
    revised = await index_current_clause_vectors(
        db=db, tenant_id=world.tenant, project_id=world.project,
        clause_ids=[str(v2_clause.id)], embed=fake_embeddings,
    )
    assert revised["indexed"] == 0
    pairs_after_proposal = await repo.find_cross_document_pairs(
        project_id=world.project, similarity_threshold=0.9, max_pairs=10,
    )
    assert len(pairs_after_proposal) == 1
    assert {pairs_after_proposal[0].source_clause_id, pairs_after_proposal[0].target_clause_id} == set(requested)
