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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import CandidateBinding, TrustState
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


    # The real worker fixture does not manufacture an analysis artifact; save
    # a genuine PROPOSED candidate before proving that all canonical readers
    # exclude it. A revision without *any* artifact would be a false green.
    artifacts = SqlAlchemyDocumentArtifactRepository(db)
    await artifacts.save(
        DocumentArtifact(
            document_id=str(uploaded.id),
            document_revision_id=str(revision.revision_id),
            doc_type="technical_spec",
        ),
        project_id=project_id,
        tenant_id=tenant_id,
        trust_state=TrustState.PROPOSED,
    )
    await db.commit()


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

    # The positive side of S2/S4 source publication was previously absent:
    # after a precisely bound candidate is trusted, current readers must see
    # EXACTLY the persisted original technical sections (never confidence,
    # compliance, WBS association or an invented coherence score).
    #
    # Repository-level test setup invokes the exact candidate CAS directly;
    # this is NOT an authenticated final HITL user flow.
    proposed_row = await db.scalar(
        select(DocumentArtifactORM)
        .where(
            DocumentArtifactORM.tenant_id == tenant_id,
            DocumentArtifactORM.document_id == uploaded.id,
            DocumentArtifactORM.document_revision_id == revision.revision_id,
            DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
        )
        .order_by(DocumentArtifactORM.artifact_version.desc())
    )
    assert proposed_row is not None
    candidate = CandidateBinding(
        artifact_id=proposed_row.artifact_id,
        document_id=uploaded.id,
        artifact_version=proposed_row.artifact_version,
        artifact_hash=proposed_row.artifact_hash,
    )
    await artifacts.commit_candidate(candidate, tenant_id=tenant_id)
    await db.commit()
    current = await SqlAlchemyCurrentRevisionResolver(db).resolve(
        tenant_id=tenant_id, document_id=uploaded.id
    )
    assert current.status is CurrentRevisionStatus.TRUSTED
    assert current.revision_id == revision.revision_id

    approved_candidates = await _get_persisted_clause_candidates(
        db, project_id, tenant_id, 50
    )
    technical_candidates = [
        clause for clause in approved_candidates
        if str(clause.data.get("document_id")) == str(uploaded.id)
    ]
    assert len(technical_candidates) == 2
    assert {clause.text for clause in technical_candidates} == set(SOURCE_SECTIONS)
    assert {
        str(clause.data["evidence_location"]["revision_id"])
        for clause in technical_candidates
    } == {str(revision.revision_id)}
    assert all(
        clause.data["technical_requirement"]["verification_status"] == "unverified"
        for clause in technical_candidates
    ), "source publication must not imply human technical verification"
    assert all(
        clause.data["category"] == "TECHNICAL"
        and clause.data["source_document_type"] == "technical_spec"
        and clause.data["assessment_unavailable"] == {
            "TECHNICAL": "TECHNICAL_SOURCE_ONLY_COMPLIANCE_UNVERIFIED"
        }
        for clause in technical_candidates
    ), "approved source is cited in Health but never treated as compliance"

    # Exercise the actual project-scoped Coherence/Health API after trusting the
    # source. A genuine (but unassessed) requirement is now present; the Health
    # must still withhold the TECHNICAL dimension and overall score.
    from tests.integration.document_flow.test_contract_schedule_completion_flow import (
        _evaluate,
    )

    health = await _evaluate(db, test_user, project_id)
    assert health.overall_score is None, "a source-only spec cannot earn a score"
    assert "TECHNICAL" in (health.score_missing_dimensions or [])
    technical_health = [
        item for item in health.category_breakdown
        if item.category in {"technical", "TECHNICAL"}
    ]
    assert technical_health, "Health must explicitly represent TECHNICAL"
    assert all(
        item.score is None and item.state == "unassessed"
        for item in technical_health
    ), "technical compliance remains unmeasured, never green or zero"

    # Trusting a source for citation never settles technical compliance.
    assert await db.scalar(
        text("SELECT count(*) FROM coherence_results WHERE project_id = :p"),
        {"p": project_id},
    ) == 0
