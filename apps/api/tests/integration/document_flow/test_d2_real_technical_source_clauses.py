"""ACC-01 D2: REAL DOCX -> real worker -> PostgreSQL technical source clauses.

Only storage, embeddings and the broker are replaced.  A source row is not
human approval, a Technical score, or WBS authority.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import docx
import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.router import (
    _get_parsed_text_fallback_clauses,
    _get_persisted_clause_candidates,
    _get_rag_chunk_clauses,
    get_clauses_from_rag,
)
from src.core.tasks import ingestion_tasks
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from tests.integration.document_flow.test_852_schedule_wbs_governance_guard import (
    _project,
    _ProjectRepo,
    worker,  # noqa: F401 - reuse real worker's isolated services
)

pytestmark = pytest.mark.asyncio

SOURCE_SECTIONS = (
    "Section 4.1.2 Concrete compressive strength shall exceed 35 MPa at 28 days.",
    "Section 4.2 Reinforcement steel shall be B500S.",
)


def _docx(lines: tuple[str, ...]) -> bytes:
    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def test_real_worker_persists_two_revision_bound_technical_sources_without_a_score(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    uploaded = await UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=worker,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=revisions,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="specification.docx", file=BytesIO(_docx(SOURCE_SECTIONS))),
        document_type=DocumentType.TECHNICAL_SPEC,
        user_id=test_user.id,
        tenant_id=tenant_id,
    )
    [revision] = await revisions.list_lineage(uploaded.id, tenant_id)

    parsed = await ingestion_tasks._process(uploaded.id, revision.revision_id)
    assert parsed["status"] == "success", parsed
    await db.commit()

    rows = (
        await db.execute(
            text(
                "SELECT clause_code, full_text, text_start_offset, text_end_offset, "
                "revision_id, extraction_confidence, manually_verified, extracted_entities "
                "FROM clauses WHERE tenant_id = :t AND document_id = :d "
                "ORDER BY clause_code"
            ),
            {"t": tenant_id, "d": uploaded.id},
        )
    ).all()
    assert [row.clause_code for row in rows] == ["4.1.2", "4.2"]
    assert all(row.revision_id == revision.revision_id for row in rows)
    assert all(row.extraction_confidence is None and not row.manually_verified for row in rows)
    for row in rows:
        assert row.full_text in SOURCE_SECTIONS
        assert row.text_end_offset > row.text_start_offset
        assert row.extracted_entities["evidence_location"]["revision_id"] == str(
            revision.revision_id
        )
        assert (
            row.extracted_entities["technical_requirement"]["verification_status"]
            == "unverified"
        )


    # A sole PROPOSED technical revision is not trusted canonical evidence.
    # C3a's single-revision fallback resolves it, so every coherence source
    # path must independently reject it until an actual approval.
    candidate_groups = (
        await _get_persisted_clause_candidates(db, project_id, tenant_id, 50),
        await _get_rag_chunk_clauses(db, project_id, tenant_id, 50),
        await _get_parsed_text_fallback_clauses(db, project_id, tenant_id),
        await get_clauses_from_rag(db, project_id, tenant_id),
    )
    for candidates in candidate_groups:
        assert all(
            str(clause.data.get("document_id")) != str(uploaded.id)
            for clause in candidates
        ), "PROPOSED technical evidence entered canonical Coherence"

    # Ingestion does not add a canonical WBS or create a coherence result.
    assert await db.scalar(
        text("SELECT count(*) FROM wbs_nodes WHERE project_id = :p"), {"p": project_id}
    ) == 0
    assert await db.scalar(
        text("SELECT count(*) FROM coherence_results WHERE project_id = :p"),
        {"p": project_id},
    ) == 0
