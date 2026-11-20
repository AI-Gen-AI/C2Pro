"""VS-1 real FastAPI HTTP → SQL verification on disposable PostgreSQL.

No live server, external tenant data, model charges or UI mocks.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.core.security import get_current_tenant_id, get_current_user_id_with_bearer
from src.documents.adapters.http.router import (
    get_document_repository,
    get_pending_review_document_ids,
    router,
)
from src.documents.domain.models import DocumentStatus, DocumentType
from tests.unit.analysis.test_vs1_n4_sql_real_pg import _setup, pg  # noqa: F401


def test_http_get_proposed_evidence_and_post_financial_stop_with_real_pg(pg):
    tenant, project, document, revision, run, digest = _setup(pg)
    doc = SimpleNamespace(
        project_id=project,
        document_type=DocumentType.CONTRACT,
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        document_metadata={
            "analysis_n4_run_id": str(run),
            "analysis_n4_revision_id": str(revision),
            "analysis_n4_source_sha256": digest,
            "analysis_last_attempt_incomplete": True,
            "analysis_blocker_code": "N4_PARTIAL_RESULTS",
        },
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant
    app.dependency_overrides[get_current_user_id_with_bearer] = lambda: uuid4()
    app.dependency_overrides[get_pending_review_document_ids] = (
        lambda: (lambda *_: {})
    )

    async def fake_document_repository():
        url = pg.url.set(
            drivername="postgresql+asyncpg",
            database=pg.url.query.get("dbname", "postgres"),
            query={"host": pg.url.query["host"], "port": pg.url.query["port"]},
        )
        engine = create_async_engine(url, pool_pre_ping=True)
        try:
            async with AsyncSession(engine) as session:
                yield SimpleNamespace(
                    session=session,
                    get_by_id=AsyncMock(return_value=doc),
                )
        finally:
            await engine.dispose()

    app.dependency_overrides[get_document_repository] = fake_document_repository

    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        response = client.get(
            f"/projects/{project}/documents/{document}/n4-findings",
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "PARTIAL_UNASSESSED"
        assert body["coverage"]["windows_with_result"] == 2
        assert body["coverage"]["examined"] == 1
        assert body["coverage"]["blocked"] == 1
        assert body["total_findings"] == 1
        assert len(body["findings"]) == 1
        assert body["findings"][0]["review_state"] == "PROPOSED"
        assert body["findings"][0]["n2_quote_status"] == "N2_EXACT_MATCH"
        assert body["findings"][0]["original_pdf_quote_status"] == "UNVERIFIED"
        assert body["approvable"] is False and body["trusted"] is False

        # No client-side control is trusted as the actual financial guard.
        blocked = client.post(
            f"/projects/{project}/documents/{document}/reprocess",
        )
        assert blocked.status_code == 409, blocked.text

        # The previous usage remains a server-side barrier even when
        # document metadata is absent due to an interrupted worker.
        doc.document_metadata = {"analysis_last_attempt_incomplete": True}
        blocked_without_metadata = client.post(
            f"/projects/{project}/documents/{document}/reprocess",
        )
        assert blocked_without_metadata.status_code == 409
        assert "Earlier N4 usage" in blocked_without_metadata.json()["detail"]

        # A browser querying a different project must not recover findings.
        foreign = client.get(
            f"/projects/{uuid4()}/documents/{document}/n4-findings",
        )
        assert foreign.status_code == 404
