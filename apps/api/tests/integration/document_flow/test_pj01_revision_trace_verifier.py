"""The Nightly's PostgreSQL read of the PJ-01 revision trace (S6) binds B's approval to B's artifact.

``verify_pj01_revision_trace.py --kind journey`` used to accept ANY approved review of the project, so the
approval of revision A satisfied the condition for revision B. It must find the review bound (by
``candidate_binding``) to B's trusted artifact and content, naming who decided and when.

REAL PostgreSQL, the real repositories and the real ``commit_candidate`` promotion; the human decision is
written as the review route writes it (status, ``approved_by``, ``approved_at``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.domain.trust import CandidateBinding, TrustState
from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_budget_revision_authority_flow import (
    _artifact,
    _reupload_and_ingest,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    COMPLETION_CLAUSE,
    PRICE_CLAUSE,
    _docx,
    _project,
    _upload_and_ingest,
    worker,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio


def _load_verifier() -> Any:
    path = Path(__file__).resolve().parents[3] / "scripts" / "verify_pj01_revision_trace.py"
    spec = importlib.util.spec_from_file_location("verify_pj01_revision_trace", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


async def _propose(
    db: AsyncSession, user: Any, project_id: UUID, document: Any, revision: Any
) -> CandidateBinding:
    """A PROPOSED candidate bound to the revision, with the pending review the repository opens for it."""
    repository = SqlAlchemyDocumentArtifactRepository(db)
    await repository.save(
        _artifact(document.id, revision.revision_id),
        project_id=project_id,
        tenant_id=user.tenant_id,
        trust_state=TrustState.PROPOSED,
    )
    row = (
        await db.execute(
            text(
                "SELECT artifact_id, artifact_version, artifact_hash FROM document_artifacts "
                "WHERE document_id = :d AND trust_state = 'proposed'"
            ),
            {"d": document.id},
        )
    ).one()
    await db.commit()
    return CandidateBinding(
        artifact_id=row.artifact_id,
        document_id=document.id,
        artifact_version=row.artifact_version,
        artifact_hash=row.artifact_hash,
    )


async def _approve(
    db: AsyncSession,
    user: Any,
    binding: CandidateBinding,
    *,
    decided_by: str | None = "reviewer@example.test",
) -> None:
    """The final human act: the review bound to this candidate is approved, then the candidate is trusted."""
    await db.execute(
        text(
            "UPDATE review_items SET current_status = 'APPROVED', approved_by = :by, "
            "approved_at = now() AT TIME ZONE 'utc' "
            "WHERE review_metadata->'candidate_binding'->>'artifact_id' = :a"
        ),
        {"by": decided_by, "a": str(binding.artifact_id)},
    )
    await SqlAlchemyDocumentArtifactRepository(db).commit_candidate(
        binding, tenant_id=user.tenant_id
    )
    await db.commit()


async def _journey(db: AsyncSession, worker: Any, user: Any) -> Any:  # noqa: F811
    """Revision A proposed and approved (trusted), then revision B proposed; B is not decided yet."""
    project_id = await _project(db, user.tenant_id)
    document, revision_a = await _upload_and_ingest(
        db,
        worker,
        user,
        project_id,
        filename="contract.docx",
        content=_docx([PRICE_CLAUSE, COMPLETION_CLAUSE]),
        document_type=DocumentType.CONTRACT,
    )
    binding_a = await _propose(db, user, project_id, document, revision_a)
    await _approve(db, user, binding_a)
    revision_b = await _reupload_and_ingest(
        db, worker, user, document, _docx([PRICE_CLAUSE, COMPLETION_CLAUSE, "Anexo. Revisión B."])
    )
    binding_b = await _propose(db, user, project_id, document, revision_b)
    hashes = (
        (
            await db.execute(
                text(
                    "SELECT blob_hash FROM document_revisions WHERE document_id = :d ORDER BY rev_no"
                ),
                {"d": document.id},
            )
        )
        .scalars()
        .all()
    )
    url = db.bind.url.render_as_string(hide_password=False)  # type: ignore[union-attr]
    return url, project_id, hashes[0], hashes[1], binding_b


async def test_a_journey_whose_revision_b_was_approved_by_a_named_reviewer_passes(
    db: AsyncSession,
    worker: Any,
    test_user: Any,  # noqa: F811
) -> None:
    url, project_id, hash_a, hash_b, binding_b = await _journey(db, worker, test_user)
    await _approve(db, test_user, binding_b)

    assert await _load_verifier().verify(url, project_id, hash_a, hash_b) == []


async def test_the_approval_of_revision_a_never_satisfies_revision_b(
    db: AsyncSession,
    worker: Any,
    test_user: Any,  # noqa: F811
) -> None:
    """B becomes trusted (e.g. a direct promotion) while its own review is still pending: A's approval is not B's."""
    url, project_id, hash_a, hash_b, binding_b = await _journey(db, worker, test_user)
    await SqlAlchemyDocumentArtifactRepository(db).commit_candidate(
        binding_b, tenant_id=test_user.tenant_id
    )
    await db.commit()

    failures = await _load_verifier().verify(url, project_id, hash_a, hash_b)

    assert any("review bound to it is not approved" in failure for failure in failures), failures


async def test_an_approval_that_names_nobody_does_not_count(
    db: AsyncSession,
    worker: Any,
    test_user: Any,  # noqa: F811
) -> None:
    url, project_id, hash_a, hash_b, binding_b = await _journey(db, worker, test_user)
    await _approve(db, test_user, binding_b, decided_by=None)

    failures = await _load_verifier().verify(url, project_id, hash_a, hash_b)

    assert any("does not name who took the decision" in failure for failure in failures), failures


async def test_an_approved_review_bound_to_other_content_does_not_count(
    db: AsyncSession,
    worker: Any,
    test_user: Any,  # noqa: F811
) -> None:
    url, project_id, hash_a, hash_b, binding_b = await _journey(db, worker, test_user)
    await _approve(db, test_user, binding_b)
    await db.execute(
        text(
            "UPDATE review_items SET review_metadata = jsonb_set("
            "review_metadata, '{candidate_binding,artifact_hash}', '\"0000\"') "
            "WHERE review_metadata->'candidate_binding'->>'artifact_id' = :a"
        ),
        {"a": str(binding_b.artifact_id)},
    )
    await db.commit()

    failures = await _load_verifier().verify(url, project_id, hash_a, hash_b)

    assert any("bound to different content" in failure for failure in failures), failures
