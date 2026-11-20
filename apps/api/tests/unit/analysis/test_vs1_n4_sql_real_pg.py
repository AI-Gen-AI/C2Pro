"""VS-1 real SQL contract tests on a disposable PostgreSQL 16 server.

No external DB, network provider or AI calls. This fixture uses a reduced
schema shaped exactly like migrations 20261116_0001/0002; it is NOT a
full application migration or browser integration test.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.documents.adapters.http.router import (
    read_n4_partial_findings, reprocess_document_endpoint,
)
from src.documents.domain.models import DocumentStatus, DocumentType
from tests.unit.analysis.test_g2_n4_crossgen_pg import pg  # noqa: F401

pytestmark = pytest.mark.asyncio


def _setup(pg):
    tenant, project, document, revision, run = (uuid4() for _ in range(5))
    digest = "a" * 64
    with pg.begin() as db:
        db.execute(text("""
            ALTER TABLE public.n4_extraction_runs
            ADD COLUMN project_id uuid,
            ADD COLUMN status varchar(16),
            ADD COLUMN total_windows integer,
            ADD COLUMN generation bigint
        """))
        db.execute(text("""
            CREATE TABLE public.document_revisions (
                revision_id uuid PRIMARY KEY,
                tenant_id uuid NOT NULL,
                document_id uuid NOT NULL,
                valid_to timestamptz
            )
        """))
        db.execute(text("""
            CREATE TABLE public.document_processing_operations (
                tenant_id uuid NOT NULL,
                document_id uuid NOT NULL,
                revision_id uuid NOT NULL,
                generation bigint NOT NULL
            )
        """))
        db.execute(text("""
            CREATE TABLE public.n4_extraction_windows (
                tenant_id uuid NOT NULL,
                run_id uuid NOT NULL,
                ordinal integer NOT NULL,
                status varchar(16) NOT NULL,
                blocked_reason varchar(80),
                unresolved_refs jsonb NOT NULL,
                committed_at timestamptz,
                findings_sha256 char(64)
            )
        """))
        db.execute(text("""
            CREATE TABLE public.n4_candidate_findings (
                tenant_id uuid NOT NULL,
                run_id uuid NOT NULL,
                window_ordinal integer NOT NULL,
                finding_key char(64) NOT NULL,
                claim jsonb NOT NULL,
                source_refs jsonb NOT NULL
            )
        """))
        db.execute(text("""
            INSERT INTO public.document_revisions(
                revision_id,tenant_id,document_id,valid_to)
            VALUES(:revision,:tenant,:document,NULL)
        """), {"revision": str(revision), "tenant": str(tenant), "document": str(document)})
        db.execute(text("""
            INSERT INTO public.document_processing_operations(
                tenant_id,document_id,revision_id,generation)
            VALUES(:tenant,:document,:revision,2)
        """), {"tenant": str(tenant), "document": str(document), "revision": str(revision)})
        db.execute(text("""
            INSERT INTO public.n4_extraction_runs(
                tenant_id, run_id, project_id, document_id,
                document_revision_id, source_sha256, status,
                total_windows, generation)
            VALUES(:tenant,:run,:project,:document,:revision,:digest,'PARTIAL',2,1)
        """), {"tenant": str(tenant), "run": str(run), "project": str(project),
                "document": str(document), "revision": str(revision), "digest": digest})
        db.execute(text("""
            INSERT INTO public.n4_extraction_windows(
                tenant_id,run_id,ordinal,status,blocked_reason,unresolved_refs,
                committed_at,findings_sha256)
            VALUES
                (:tenant,:run,0,'BLOCKED','REFERENCES_UNRESOLVED',
                 '["Annex III"]'::jsonb,clock_timestamp(),:digest),
                (:tenant,:run,1,'EXAMINED',NULL,
                 '[]'::jsonb,clock_timestamp(),:digest)
        """), {"tenant": str(tenant), "run": str(run), "digest": digest})
        db.execute(text("""
            INSERT INTO public.n4_candidate_findings(
                tenant_id,run_id,window_ordinal,finding_key,claim,source_refs)
            VALUES(
                :tenant,:run,0,:key,
                CAST(:claim AS jsonb),CAST(:refs AS jsonb))
        """), {
            "tenant": str(tenant), "run": str(run),
            "key": "e" * 64,
            "claim": __import__("json").dumps({
                "title": "FAT milestone", "risk_reason": "Annex III missing",
                "source_quote": "The FAT shall be inspected",
                "source_evidence_status": "EXACT_MODEL_SAFE_MATCH",
                "clause_ref": "4.3",
            }),
            "refs": __import__("json").dumps([{
                "source_kind": "MODEL_SAFE_PROJECTION",
                "document_revision_id": str(revision),
                "source_sha256": digest,
                "evidence_status": "EXACT_MODEL_SAFE_MATCH",
                "analysis_span": [0, 26],
            }])
        })
        db.execute(text("""
            INSERT INTO public.n4_usage_reservations(tenant_id,run_id,status)
            VALUES(:tenant,:run,'SETTLED')
        """), {"tenant": str(tenant), "run": str(run)})
    return tenant, project, document, revision, run, digest


async def _engine(pg):
    return create_async_engine(
        str(pg.url).replace("postgresql+psycopg", "postgresql+asyncpg"),
        pool_pre_ping=True,
    )


async def test_get_real_postgres_coverage_pagination_and_stale_revision(pg):
    tenant, project, document, revision, run, digest = _setup(pg)
    engine = await _engine(pg)
    try:
        async with AsyncSession(engine) as session:
            doc = SimpleNamespace(
                project_id=project,
                document_metadata={
                    "analysis_n4_run_id": str(run),
                    "analysis_n4_revision_id": str(revision),
                    "analysis_n4_source_sha256": digest,
                },
            )
            repo = SimpleNamespace(session=session, get_by_id=AsyncMock(return_value=doc))
            result = await read_n4_partial_findings(
                project, document, uuid4(), tenant, offset=0, limit=100, repo=repo,
            )
            assert result["status"] == "PARTIAL_UNASSESSED"
            assert result["coverage"]["windows_with_result"] == 2
            assert result["coverage"]["examined"] == 1
            assert result["coverage"]["blocked"] == 1
            assert result["coverage"]["windows"][0]["unresolved_refs"] == ["Annex III"]
            assert result["total_findings"] == 1
            assert result["findings"][0]["n2_quote_status"] == "N2_EXACT_MATCH"
            assert result["findings"][0]["source_quote"] == "The FAT shall be inspected"
            assert result["findings"][0]["interpretation"] == "Annex III missing"
            assert result["findings"][0]["original_pdf_quote_status"] == "UNVERIFIED"
            assert not result["approvable"] and not result["trusted"]
            assert (await read_n4_partial_findings(
                project, document, uuid4(), tenant, offset=1, limit=1, repo=repo,
            ))["findings"] == []
            with pytest.raises(HTTPException) as foreign:
                await read_n4_partial_findings(
                    uuid4(), document, uuid4(), tenant, offset=0, limit=100, repo=repo,
                )
            assert foreign.value.status_code == 404
            with pytest.raises(HTTPException) as foreign_tenant:
                await read_n4_partial_findings(
                    project, document, uuid4(), uuid4(), offset=0, limit=100, repo=repo,
                )
            assert foreign_tenant.value.status_code == 404
            await session.rollback()
        with pg.begin() as db:
            db.execute(text("""
                UPDATE public.document_revisions SET valid_to=clock_timestamp()
                 WHERE revision_id=:revision
            """), {"revision": str(revision)})
        async with AsyncSession(engine) as session:
            repo.session = session
            with pytest.raises(HTTPException) as outdated:
                await read_n4_partial_findings(
                    project, document, uuid4(), tenant, offset=0, limit=100, repo=repo,
                )
            assert outdated.value.status_code == 404
    finally:
        await engine.dispose()


async def test_http_reprocess_rejects_receipt_even_without_blocker_metadata(pg):
    tenant, project, document, revision, run, digest = _setup(pg)
    engine = await _engine(pg)
    try:
        async with AsyncSession(engine) as session:
            doc = SimpleNamespace(
                project_id=project, document_type=DocumentType.CONTRACT,
                document_metadata={},
                upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            )
            repo = SimpleNamespace(
                session=session, get_by_id=AsyncMock(return_value=doc),
                update_status=AsyncMock(), begin_processing_generation=AsyncMock(),
                commit=AsyncMock(),
            )
            with pytest.raises(HTTPException) as blocked:
                await reprocess_document_endpoint(
                    project, document, uuid4(), tenant,
                    repo=repo, pending_review_lookup=lambda *_: {},
                )
            assert blocked.value.status_code == 409
            repo.update_status.assert_not_awaited()
            repo.begin_processing_generation.assert_not_awaited()
            repo.commit.assert_not_awaited()
    finally:
        await engine.dispose()
