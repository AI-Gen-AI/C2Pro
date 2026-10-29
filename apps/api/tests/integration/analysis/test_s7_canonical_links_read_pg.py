"""S7: persisted explicit canonical event, trusted-current read after new HTTP sessions."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.http import technical_wbs_review_router as router
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.documents.adapters.persistence.models import ClauseORM
from src.analysis.application.approve_canonical_technical_wbs_link import (
    CANONICAL_APPROVAL,
    ApproveCanonicalTechnicalWBSLinkService,
)
from src.analysis.application.record_technical_wbs_review import RecordTechnicalWBSReviewService
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from tests.integration.analysis.test_s7_review_service_settlement_pg import (
    _arguments,
    _world,
)

pytestmark = pytest.mark.asyncio


async def test_s7_canonical_get_reloads_persisted_approved_link_and_marks_stale_source(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w = await _world(db, tmp_path)
    actor = await db.get(User, w["actor"])
    assert actor is not None and actor.clerk_user_id

    app = FastAPI()
    app.include_router(router.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: actor
    endpoint = f"/api/v1/projects/{w['project']}/technical-wbs/canonical-links"

    # Audited does not mean approved, even after refreshing the browser.
    async with test_session_factory() as audit_session:
        audit = await RecordTechnicalWBSReviewService(
            audit_session, w["reader"]
        ).execute(**_arguments(w))
        await audit_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get(endpoint)
        assert before.status_code == 200, before.text
        assert before.json() == []

    # An explicit second human action persists the *distinct* event.
    async with test_session_factory() as approval_session:
        receipt = await ApproveCanonicalTechnicalWBSLinkService(
            approval_session
        ).execute(
            tenant_id=w["tenant"],
            project_id=w["project"],
            actor_user_id=w["actor"],
            review_event_id=audit.event_id,
            expected_wbs_baseline_id=w["baseline"],
            expected_wbs_node_id=w["node"],
            approval=CANONICAL_APPROVAL,
            idempotency_key="s7-projection-pg-idempotency",
            reason="Final approval of exact trusted technical source",
        )
        await approval_session.commit()

    # Entirely new session and authenticated GET; not a cached mutation DTO.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        result = await client.get(endpoint)
        assert result.status_code == 200, result.text
        [link] = result.json()
        assert link["event_id"] == str(receipt.event_id)
        assert link["review_event_id"] == str(audit.event_id)
        assert link["technical_document_id"] == str(w["document"])
        assert link["technical_revision_id"] == str(w["revision"])
        assert link["source_clause_id"] == str(w["clause"])
        assert link["source_blob_hash"] == w["digest"]
        assert link["wbs_baseline_id"] == str(w["baseline"])
        assert link["wbs_node_id"] == str(w["node"])
        assert link["wbs_code"] == "1.1"
        assert link["state"] == "CURRENT"
        assert link["authority"] == "EXPLICIT_HUMAN_CANONICAL_LINK"
        assert link["approved_canonical_link"] is True
        assert link["technical_assessment"] == "NOT_ASSESSED"

    # A future source revision supersedes the trusted artifact. Immutable
    # approval stays in history but cannot be displayed as current.
    async with test_session_factory() as updater:
        artifact = await updater.scalar(
            select(DocumentArtifactORM).where(
                DocumentArtifactORM.tenant_id == w["tenant"],
                DocumentArtifactORM.project_id == w["project"],
                DocumentArtifactORM.document_revision_id == w["revision"],
                DocumentArtifactORM.trust_state == "trusted",
                DocumentArtifactORM.lifecycle_status == "active",
            )
        )
        assert artifact is not None
        artifact.trust_state = "superseded"
        artifact.lifecycle_status = "superseded"
        await updater.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stale = await client.get(endpoint)
        assert stale.status_code == 200, stale.text
        [historic] = stale.json()
        assert historic["event_id"] == str(receipt.event_id)
        assert historic["state"] == "STALE_SOURCE"
        assert historic["technical_assessment"] == "NOT_ASSESSED"
        assert (await client.get(endpoint, params={"limit": 51})).status_code == 422

    # A different tenant's authenticated principal never learns this project
    # or the existence of its canonical approvals (neutral 404).
    foreign = User(
        id=uuid4(), tenant_id=uuid4(),
        email=f"s7-canonical-foreign-{uuid4().hex}@example.invalid",
        clerk_user_id=f"clerk-canonical-foreign-{uuid4().hex}",
        is_active=True, is_verified=False,
    )
    app.dependency_overrides[get_current_user] = lambda: foreign
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get(endpoint)
        assert denied.status_code == 404, denied.text
        assert denied.json()["detail"] == "Project not found"


async def test_s7_canonical_read_fails_closed_on_reindexed_source_offsets(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    """The immutable approval remains, but a changed ClauseORM is not current."""
    w = await _world(db, tmp_path)
    actor = await db.get(User, w["actor"])
    assert actor is not None
    app = FastAPI()
    app.include_router(router.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: actor
    endpoint = f"/api/v1/projects/{w['project']}/technical-wbs/canonical-links"

    async with test_session_factory() as review_session:
        audit = await RecordTechnicalWBSReviewService(
            review_session, w["reader"]
        ).execute(**_arguments(w))
        await review_session.commit()
    async with test_session_factory() as approval_session:
        await ApproveCanonicalTechnicalWBSLinkService(approval_session).execute(
            tenant_id=w["tenant"],
            project_id=w["project"],
            actor_user_id=w["actor"],
            review_event_id=audit.event_id,
            expected_wbs_baseline_id=w["baseline"],
            expected_wbs_node_id=w["node"],
            approval=CANONICAL_APPROVAL,
            idempotency_key="s7-read-proof-offset-key",
            reason="Human approves source section and exact offsets",
        )
        await approval_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get(endpoint)
        assert first.status_code == 200, first.text
        assert first.json()[0]["state"] == "CURRENT"

    # Simulate a re-indexing regression on the synthetic source clause. The
    # revision identity, blob hash and artifact remain valid, but the excerpt
    # offsets no longer describe the source the human reviewed.
    async with test_session_factory() as edit_session:
        clause = await edit_session.scalar(
            select(ClauseORM).where(
                ClauseORM.id == w["clause"],
                ClauseORM.tenant_id == w["tenant"],
                ClauseORM.project_id == w["project"],
            )
        )
        assert clause is not None
        assert clause.text_start_offset == 0
        clause.text_start_offset = 1
        await edit_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        after = await client.get(endpoint)
        assert after.status_code == 200, after.text
        assert len(after.json()) == 1
        assert after.json()[0]["state"] == "STALE_SOURCE"
        assert after.json()[0]["technical_assessment"] == "NOT_ASSESSED"
