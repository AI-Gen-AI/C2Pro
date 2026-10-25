"""The budget a coherence rule reads is the TRUSTED-CURRENT revision's declaration (#1108 P1).

REAL PostgreSQL and the REAL ingestion worker. A budget document is revised: revision A is
accepted, revision B is re-uploaded and ingested before (or without) approval. The declared total
and its denominations are bound to the revision that declared them and are read only for the
revision the C3a authority (``document_artifacts`` + lineage) names current:

* A trusted, B proposed or rejected with another total -> A's figures keep driving CONBUD/NEGMARGIN;
* B approved -> B's figures apply, atomically (total and currencies never mix across revisions);
* B approved but declaring no total -> UNKNOWN, never A's figure;
* an unstamped (legacy / mutable-blob) total is never evidence;
* another tenant or another project never feeds the reading; a re-run of the same ingestion is idempotent.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any
from uuid import uuid4

import openpyxl
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import TrustState
from src.coherence.budget_clause_builder import build_budget_clauses
from src.core.tasks import ingestion_tasks
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.budget_stated_total import (
    STATED_TOTAL_BY_REVISION_KEY,
    record_revision_stated_total,
)
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    _project,
    _upload_and_ingest,
    worker,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio


def _budget_xlsx(total: float | None) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total"])
    sheet.append(["Obra civil", 1, "ud", 1000, 1000])
    if total is not None:
        sheet.append(["Total presupuesto", None, None, None, total])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _artifact(document_id: Any, revision_id: Any) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_id),
        doc_type="contract",
        extracted_risks=[RiskItem(title="r", description="d")],
    )


async def _reupload_and_ingest(
    db: AsyncSession, storage: Any, user: Any, document: Any, content: bytes
) -> Any:
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    await ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        revision_repository=revisions,
        storage_service=storage,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(tenant_id=user.tenant_id, document_id=document.id, file_content=content, user_id=user.id)
    revision = (await revisions.list_lineage(document.id, user.tenant_id))[-1]
    result = await ingestion_tasks._process(document.id, revision.revision_id)
    assert result["status"] == "success", result
    return revision


async def _trust(db: AsyncSession, user: Any, project_id: Any, document: Any, revision: Any) -> None:
    """Approval: a TRUSTED artifact bound to exactly ``revision`` (it supersedes the previous one)."""
    await SqlAlchemyDocumentArtifactRepository(db).save(
        _artifact(document.id, revision.revision_id), project_id=project_id, tenant_id=user.tenant_id
    )
    await db.commit()


async def _propose(db: AsyncSession, user: Any, project_id: Any, document: Any, revision: Any) -> None:
    await SqlAlchemyDocumentArtifactRepository(db).save(
        _artifact(document.id, revision.revision_id),
        project_id=project_id,
        tenant_id=user.tenant_id,
        trust_state=TrustState.PROPOSED,
    )
    await db.commit()


async def _reject_proposed(db: AsyncSession, document: Any) -> None:
    await db.execute(
        text("UPDATE document_artifacts SET trust_state = 'rejected' "
             "WHERE document_id = :d AND trust_state = 'proposed'"),
        {"d": document.id},
    )
    await db.commit()


async def _declared_total(db: AsyncSession, project_id: Any, user: Any) -> float | None:
    await db.commit()
    [clause, *_] = [*(await build_budget_clauses(db, project_id, user.tenant_id)), None]
    return None if clause is None else clause.data["stated_total"]


async def _accepted_budget(db: AsyncSession, worker: Any, user: Any, total: float = 1_000_000) -> tuple[Any, Any, Any]:
    project_id = await _project(db, user.tenant_id)
    document, revision_a = await _upload_and_ingest(
        db, worker, user, project_id, filename="budget.xlsx",
        content=_budget_xlsx(total), document_type=DocumentType.BUDGET,
    )
    await _trust(db, user, project_id, document, revision_a)
    return project_id, document, revision_a


async def test_the_accepted_revisions_total_is_what_coherence_reads(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, _document, _a = await _accepted_budget(db, worker, test_user)

    assert await _declared_total(db, project_id, test_user) == 1_000_000


@pytest.mark.parametrize("fate", ["proposed", "rejected"])
async def test_a_proposed_or_rejected_reupload_never_moves_the_reading(
    db: AsyncSession, worker: Any, test_user: Any, fate: str
) -> None:
    project_id, document, _a = await _accepted_budget(db, worker, test_user)

    revision_b = await _reupload_and_ingest(db, worker, test_user, document, _budget_xlsx(2_000_000))
    await _propose(db, test_user, project_id, document, revision_b)
    if fate == "rejected":
        await _reject_proposed(db, document)

    # B is ingested (its own entry exists) but A is still the authority.
    metadata = (await db.execute(
        text("SELECT document_metadata FROM documents WHERE id = :d"), {"d": document.id}
    )).scalar_one()
    assert str(revision_b.revision_id) in metadata[STATED_TOTAL_BY_REVISION_KEY]
    assert await _declared_total(db, project_id, test_user) == 1_000_000, (
        f"a {fate} revision must not drive CONBUD/NEGMARGIN"
    )


async def test_approving_the_reupload_switches_to_its_figures(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, document, _a = await _accepted_budget(db, worker, test_user)
    revision_b = await _reupload_and_ingest(db, worker, test_user, document, _budget_xlsx(2_000_000))
    await _propose(db, test_user, project_id, document, revision_b)
    assert await _declared_total(db, project_id, test_user) == 1_000_000

    await _trust(db, test_user, project_id, document, revision_b)

    assert await _declared_total(db, project_id, test_user) == 2_000_000


async def test_an_approved_revision_without_a_total_is_unknown_not_the_old_figure(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, document, _a = await _accepted_budget(db, worker, test_user)
    revision_b = await _reupload_and_ingest(db, worker, test_user, document, _budget_xlsx(None))
    await _trust(db, test_user, project_id, document, revision_b)

    assert await _declared_total(db, project_id, test_user) is None, "A's total must not be inherited"


async def test_an_unstamped_total_is_not_evidence(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """The legacy flat keys (and an entry whose stamp disagrees with its key) carry no provenance."""
    project_id, document, revision_a = await _accepted_budget(db, worker, test_user)
    flat_only = {"stated_total": 9_999_999.0, "stated_total_currencies": ["USD"]}
    forged = {STATED_TOTAL_BY_REVISION_KEY: {str(revision_a.revision_id): {
        "revision_id": str(uuid4()), "total": 9_999_999.0, "currencies": ["USD"],
    }}}
    for metadata in (flat_only, forged):
        await db.execute(
            text("UPDATE documents SET document_metadata = CAST(:m AS jsonb) WHERE id = :d"),
            {"m": json.dumps(metadata), "d": document.id},
        )
        await db.commit()
        assert await _declared_total(db, project_id, test_user) is None


async def test_total_and_currencies_come_from_one_revision(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, document, revision_a = await _accepted_budget(db, worker, test_user)
    revision_b = await _reupload_and_ingest(db, worker, test_user, document, _budget_xlsx(2_000_000))
    metadata: dict[str, Any] = {}
    record_revision_stated_total(metadata, revision_id=revision_a.revision_id, blob_hash=None,
                                 total=1_000_000, currencies=["EUR"])
    record_revision_stated_total(metadata, revision_id=revision_b.revision_id, blob_hash=None,
                                 total=2_000_000, currencies=["USD"])
    await db.execute(
        text("UPDATE documents SET document_metadata = CAST(:m AS jsonb) WHERE id = :d"),
        {"m": json.dumps(metadata), "d": document.id},
    )
    await db.commit()
    await _propose(db, test_user, project_id, document, revision_b)

    [clause] = await build_budget_clauses(db, project_id, test_user.tenant_id)
    assert (clause.data["stated_total"], clause.data.get("budget_currencies")) == (1_000_000.0, None)

    await db.execute(
        text("UPDATE document_artifacts SET trust_state = 'rejected' WHERE document_id = :d "
             "AND trust_state = 'proposed'"), {"d": document.id},
    )
    await _trust(db, test_user, project_id, document, revision_b)
    # B's entry is read whole: its total with ITS denomination, nothing from A.
    declaration = (await db.execute(
        text("SELECT document_metadata->'stated_total_by_revision'->:r FROM documents WHERE id = :d"),
        {"r": str(revision_b.revision_id), "d": document.id},
    )).scalar_one()
    assert (declaration["total"], declaration["currencies"]) == (2_000_000, ["USD"])
    [clause_b] = await build_budget_clauses(db, project_id, test_user.tenant_id)
    assert clause_b.data["stated_total"] == 2_000_000.0


async def test_another_tenants_or_projects_budget_never_feeds_the_reading(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, _document, _a = await _accepted_budget(db, worker, test_user, total=1_000_000)
    other_project = await _project(db, test_user.tenant_id)

    assert await _declared_total(db, other_project, test_user) is None, "another project"
    assert await build_budget_clauses(db, project_id, uuid4()) == [], "another tenant"


async def test_reingesting_the_same_revision_is_idempotent(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, document, revision_a = await _accepted_budget(db, worker, test_user)
    for _ in range(2):
        # The worker fences a revision it already ingested; either way nothing is duplicated or lost.
        outcome = await ingestion_tasks._process(document.id, revision_a.revision_id)
        assert outcome["status"] in {"success", "already_ingested"}, outcome

    metadata = (await db.execute(
        text("SELECT document_metadata FROM documents WHERE id = :d"), {"d": document.id}
    )).scalar_one()
    assert list(metadata[STATED_TOTAL_BY_REVISION_KEY]) == [str(revision_a.revision_id)]
    assert "stated_total" not in metadata
    assert await _declared_total(db, project_id, test_user) == 1_000_000
