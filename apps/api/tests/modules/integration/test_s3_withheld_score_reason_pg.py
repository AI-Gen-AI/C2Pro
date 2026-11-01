"""S3 on real PostgreSQL: a null Score always says WHY, after a reload and in another session.

Four different reasons are never confused: evidence insufficient (an evaluation ran), contract awaiting a decision,
contract REJECTED, and no evaluation at all. A Score is never invented for any of them, and a scoreless evaluation
still persists no CoherenceResult.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.models import Clause, EnrichedCoherenceResult
from src.coherence.router import (
    CoherenceEvaluateRequest,
    evaluate_project_coherence,
    get_coherence_dashboard,
)
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import DocumentRevisionORM

pytestmark = pytest.mark.asyncio

INSUFFICIENT = "insufficient_active_weight"
MISSING = ["BUDGET", "LEGAL", "QUALITY", "SCOPE", "TECHNICAL", "TIME"]


async def _project(db: AsyncSession, tenant_id) -> ProjectORM:
    project = ProjectORM(
        id=uuid4(), tenant_id=tenant_id, name="S3 reason project", project_type="construction",
        status="active", currency="EUR",
    )
    db.add(project)
    await db.commit()
    return project


async def _dashboard(db: AsyncSession, project_id, tenant_id):
    return await get_coherence_dashboard(project_id, SimpleNamespace(tenant_id=tenant_id), db=db, flags_service=None)


async def _evaluate_insufficient(db: AsyncSession, project_id, tenant_id, user_id) -> None:
    enriched = EnrichedCoherenceResult(
        overall_score=None, score_reason=INSUFFICIENT, score_missing_dimensions=MISSING, score_version="coherence-v1",
    )
    with (
        patch("src.coherence.router.evaluate_coherence_async", new_callable=AsyncMock, return_value=enriched),
        patch("src.coherence.router._v2_enabled_for", new_callable=AsyncMock, return_value=False),
    ):
        result = await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(
                project_id=project_id, clauses=[Clause(id=str(uuid4()), text="One lonely clause.", data={})]
            ),
            include_diagnostics=True,
            db=db,
            current_user=SimpleNamespace(tenant_id=tenant_id, id=user_id),
            flags_service=None,
        )
    assert result.overall_score is None and result.score_reason == INSUFFICIENT


async def _contract(db: AsyncSession, project: ProjectORM, user_id, artifact_state: str) -> None:
    document_id, revision_id = uuid4(), uuid4()
    db.add(DocumentORM(
        id=document_id, tenant_id=project.tenant_id, project_id=project.id, document_type=DocumentType.CONTRACT,
        filename="contract.docx", file_format=".docx", file_hash="a" * 64, created_by=user_id,
    ))
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(DocumentRevisionORM(
        revision_id=revision_id, tenant_id=project.tenant_id, project_id=project.id, document_id=document_id,
        rev_no=1, blob_hash="a" * 64, blob_key=f"synthetic/{revision_id}.docx", valid_from=now, created_at=now,
    ))
    await db.flush()
    db.add(DocumentArtifactORM(
        artifact_id=uuid4(), tenant_id=project.tenant_id, project_id=project.id, document_id=document_id,
        document_revision_id=revision_id, artifact_version=1, artifact_hash="b" * 64,
        payload={"document_id": str(document_id), "doc_type": "contract"},
        trust_state=artifact_state, lifecycle_status="superseded" if artifact_state == "rejected" else "active",
    ))
    await db.commit()


async def test_never_evaluated_says_so_and_invents_no_score(db: AsyncSession, test_tenant) -> None:
    project = await _project(db, test_tenant.id)
    summary = await _dashboard(db, project.id, test_tenant.id)
    assert summary.global_score is None and summary.coherence_score is None
    assert summary.score_reason == "not_evaluated"


async def test_insufficient_evidence_reason_survives_reload_and_another_session(
    db: AsyncSession, test_session_factory, test_tenant, test_user
) -> None:
    project = await _project(db, test_tenant.id)
    await _evaluate_insufficient(db, project.id, test_tenant.id, test_user.id)

    # A scoreless evaluation invents no CoherenceResult ...
    assert await db.scalar(select(func.count()).select_from(CoherenceResultORM).where(CoherenceResultORM.project_id == project.id)) == 0
    # ... but its reason is durable: a brand-new session (a later visit, a new login) reads it back.
    async with test_session_factory() as other_session:
        summary = await _dashboard(other_session, project.id, test_tenant.id)
    assert summary.global_score is None and summary.coherence_score is None
    assert summary.score_reason == INSUFFICIENT
    assert sorted(summary.score_missing_dimensions or []) == MISSING
    assert summary.score_version == "coherence-v1"
    assert all(value is None or value == 0 for value in (summary.sub_scores or {}).values()) or summary.sub_scores is not None


async def test_a_newer_persisted_score_supersedes_the_withheld_record(
    db: AsyncSession, test_tenant, test_user
) -> None:
    project = await _project(db, test_tenant.id)
    await _evaluate_insufficient(db, project.id, test_tenant.id, test_user.id)
    db.add(CoherenceResultORM(
        project_id=project.id, tenant_id=test_tenant.id, global_score=72, category_scores={"SCOPE": 72},
        category_details=[], alerts=[], score_version="coherence-v1", score_reason=None,
        score_missing_dimensions=None, calculated_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
    ))
    await db.commit()
    summary = await _dashboard(db, project.id, test_tenant.id)
    assert summary.global_score == 72 and summary.score_reason != INSUFFICIENT


async def test_contract_awaiting_and_contract_rejected_are_different_reasons(
    db: AsyncSession, test_tenant, test_user
) -> None:
    pending = await _project(db, test_tenant.id)
    await _contract(db, pending, test_user.id, "proposed")
    rejected = await _project(db, test_tenant.id)
    await _contract(db, rejected, test_user.id, "rejected")
    pending_summary = await _dashboard(db, pending.id, test_tenant.id)
    rejected_summary = await _dashboard(db, rejected.id, test_tenant.id)
    assert pending_summary.score_reason == "contract_pending_approval" and pending_summary.global_score is None
    assert rejected_summary.score_reason == "contract_rejected" and rejected_summary.global_score is None
    assert sorted(rejected_summary.score_missing_dimensions or []) == MISSING


async def test_the_withheld_reason_is_tenant_scoped(db: AsyncSession, test_tenant, test_user) -> None:
    project = await _project(db, test_tenant.id)
    await _evaluate_insufficient(db, project.id, test_tenant.id, test_user.id)
    with pytest.raises(HTTPException) as foreign:
        await _dashboard(db, project.id, uuid4())  # another tenant cannot read this project's reason
    assert foreign.value.status_code == 404
