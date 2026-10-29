"""S7 read-after-relogin: actual PostgreSQL event + live current authority.

No test-specific fake event or mocked trusted revision: review and approval are
settled by the production services in independent real PostgreSQL sessions.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.approve_canonical_technical_wbs_link import (
    CANONICAL_APPROVAL,
    ApproveCanonicalTechnicalWBSLinkService,
)
from src.analysis.application.list_canonical_technical_wbs_links import (
    CanonicalLinkProjectNotFound,
    ListCanonicalTechnicalWBSLinksService,
)
from src.analysis.application.record_technical_wbs_review import (
    RecordTechnicalWBSReviewService,
)
from src.temporal.adapters.persistence.models import ProjectEventORM
from tests.integration.analysis.test_s7_review_service_settlement_pg import (
    _arguments,
    _world,
)

pytestmark = pytest.mark.asyncio


async def _approved_world(db, test_session_factory, tmp_path):
    world = await _world(db, tmp_path)
    async with test_session_factory() as session:
        review = await RecordTechnicalWBSReviewService(
            session, world["reader"]
        ).execute(**_arguments(world))
        await session.commit()

    args = {
        "tenant_id": world["tenant"],
        "project_id": world["project"],
        "actor_user_id": world["actor"],
        "review_event_id": review.event_id,
        "expected_wbs_baseline_id": world["baseline"],
        "expected_wbs_node_id": world["node"],
        "approval": CANONICAL_APPROVAL,
        "idempotency_key": "s7-list-canonical-pg-key",
        "reason": "Reviewer approves an exact technical source to WBS",
    }
    async with test_session_factory() as session:
        result = await ApproveCanonicalTechnicalWBSLinkService(session).execute(**args)
        await session.commit()
    return world, review, result


async def test_s7_reader_rehydrates_current_approval_after_new_database_session(
    db: AsyncSession, test_session_factory, tmp_path,
) -> None:
    world, review, approved = await _approved_world(db, test_session_factory, tmp_path)

    # A fresh reader, equivalent to reload/relogin at the data layer. No
    # in-memory UI state or an uncommitted writer session is consulted.
    async with test_session_factory() as fresh_login:
        rows = await ListCanonicalTechnicalWBSLinksService(fresh_login).execute(
            tenant_id=world["tenant"], project_id=world["project"],
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.event_id == approved.event_id
        assert row.review_event_id == review.event_id
        assert row.technical_revision_id == world["revision"]
        assert row.source_clause_id == world["clause"]
        assert row.wbs_baseline_id == world["baseline"]
        assert row.wbs_node_id == world["node"]
        assert row.current_state == "CURRENT_VERIFIED"
        assert row.state_reason == "CURRENT_VERIFIED"
        assert row.technical_assessment == "NOT_ASSESSED"

    # Foreign tenant must not read project existence or approval metadata.
    async with test_session_factory() as foreign_login:
        with pytest.raises(CanonicalLinkProjectNotFound):
            await ListCanonicalTechnicalWBSLinksService(foreign_login).execute(
                tenant_id=uuid4(), project_id=world["project"],
            )

    # The read path itself never writes another canonical event.
    async with test_session_factory() as inspector:
        rows = (
            await inspector.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == world["tenant"],
                    ProjectEventORM.project_id == world["project"],
                    ProjectEventORM.event_type == "technical.wbs_link_approved",
                )
            )
        ).all()
        assert len(rows) == 1


async def test_s7_reader_never_presents_superseded_source_artifact_as_current(
    db: AsyncSession, test_session_factory, tmp_path,
) -> None:
    world, _, approved = await _approved_world(db, test_session_factory, tmp_path)
    async with test_session_factory() as session:
        await session.execute(
            update(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.tenant_id == world["tenant"],
                DocumentArtifactORM.project_id == world["project"],
                DocumentArtifactORM.document_revision_id == world["revision"],
            )
            .values(trust_state="superseded", lifecycle_status="superseded")
        )
        await session.commit()

    async with test_session_factory() as fresh_login:
        rows = await ListCanonicalTechnicalWBSLinksService(fresh_login).execute(
            tenant_id=world["tenant"], project_id=world["project"],
        )
        assert len(rows) == 1
        assert rows[0].event_id == approved.event_id
        assert rows[0].current_state == "HISTORICAL_NOT_CURRENT"
        assert rows[0].state_reason == "TECHNICAL_REVISION_NOT_TRUSTED"
