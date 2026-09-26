"""
C2PRO P0b PROD HITL PERSISTENCE hotfix -- Objective A: review row identity.

Production evidence: find_active_review() successfully returned an active
legacy review, but the immediately following update_review_item() call
raised on that same row (checkpoint_id_persist_failed).

Root cause: ReviewItemORM.item_id is a BUSINESS identifier, not a unique
one -- for review_type="analysis_critique", human_interrupt_node sets it to
document_id, so every review ever created for one document (including the
pre-fix duplicates production has) shares the same item_id. Both
find_active_review() and update_review_item() queried by item_id alone;
find_active_review() narrowed correctly (status filter + "most recent"
tie-break), but update_review_item()'s bare
``select(...).where(item_id == ...)`` + ``scalar_one_or_none()`` raised
MultipleResultsFound against that same duplicate set.

Fixed by threading the row's actual primary key (ReviewItemORM.id) through
the domain layer as metadata["row_id"] (see repository.py's _to_domain),
and having update_review_item() key off it when present.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.core.auth.models import Tenant
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


async def _seed_legacy_duplicates(db, *, count: int = 4) -> tuple[UUID, UUID, UUID]:
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()

    db.add(
        Tenant(
            id=tenant_id,
            name="Row Identity Hotfix Tenant",
            slug=f"row-identity-{tenant_id.hex[:8]}",
            subscription_plan="professional",
            is_active=True,
        )
    )
    await db.commit()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="Row Identity Hotfix Project",
            code="ROW-ID",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    db.add(
        DocumentORM(
            id=document_id,
            tenant_id=tenant_id,
            project_id=project_id,
            document_type="contract",
            filename="row-identity.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()

    # Exactly the production shape: item_id = document_id (per
    # human_interrupt_node), thread_id=NULL, checkpoint_id=NULL, PENDING.
    for i in range(count):
        db.add(
            ReviewItemORM(
                id=uuid4(),
                item_id=document_id,
                item_type="contract",
                current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
                confidence=0.0,
                impact_level=ImpactLevel.HIGH,
                tenant_id=tenant_id,
                sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3),
                item_data={},
                review_metadata={},
                checkpoint_id=None,
                thread_id=None,
                project_id=project_id,
                document_id=document_id,
                review_type="analysis_critique",
                created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=count - i),
            )
        )
    await db.commit()
    return tenant_id, project_id, document_id


async def test_update_review_item_updates_the_exact_row_find_active_review_returned(
    db,
) -> None:
    tenant_id, _project_id, document_id = await _seed_legacy_duplicates(db)
    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)

    found = await repo.find_active_review(document_id=document_id, review_type="analysis_critique")
    assert found is not None
    assert "row_id" in found.metadata, "the persistent row identity must survive _to_domain"

    found.metadata["checkpoint_id"] = "real-checkpoint-row-identity"
    found.metadata["thread_id"] = f"document:{document_id}:analysis"

    # Must not raise MultipleResultsFound (or anything else) against the
    # legacy-duplicate shape.
    await repo.update_review_item(found)

    rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document_id))
    ).scalars().all()
    assert len(rows) == 4, "update must never create a 5th row"

    updated = [r for r in rows if r.checkpoint_id is not None]
    assert len(updated) == 1, "exactly one row may end up carrying the new checkpoint_id"
    assert updated[0].id == UUID(found.metadata["row_id"]), (
        "the row that got updated must be the EXACT row find_active_review returned"
    )
    assert updated[0].thread_id == f"document:{document_id}:analysis"

    untouched = [r for r in rows if r.id != updated[0].id]
    assert len(untouched) == 3
    assert all(r.checkpoint_id is None and r.thread_id is None for r in untouched), (
        "legacy rows not chosen for adoption must be left exactly as they were"
    )


async def test_get_review_item_resolves_legacy_duplicates_instead_of_raising(db) -> None:
    """ResumeWorkflowUseCase's get_review_item(review_id) call must not
    crash when legacy duplicate rows share the item_id it is given --
    it must resolve deterministically (most recently created), the same
    row find_active_review would pick for that item_id/status shape.
    """
    tenant_id, _project_id, document_id = await _seed_legacy_duplicates(db)
    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)

    found_by_item_id = await repo.get_review_item(document_id)
    assert found_by_item_id is not None

    found_active = await repo.find_active_review(
        document_id=document_id, review_type="analysis_critique"
    )
    assert found_active is not None
    assert found_by_item_id.metadata["row_id"] == found_active.metadata["row_id"], (
        "get_review_item and find_active_review must agree on which row is active"
    )
