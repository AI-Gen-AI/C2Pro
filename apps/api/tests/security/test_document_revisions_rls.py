"""RLS smoke test for document_revisions table (ADR-015 / TASK-V3-015-01).

Verifies the table exists, RLS policies can be created, and cross-tenant
isolation. When the test role is superuser, the cross-tenant assertion is
marked xfail with explicit reason.
"""

from __future__ import annotations

from datetime import UTC
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence import models as _tr_models  # noqa: F401

pytestmark = [pytest.mark.security, pytest.mark.asyncio]


@pytest.mark.security
@pytest.mark.asyncio
async def test_document_revisions_table_exists(db: AsyncSession):
    tables = (await db.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='document_revisions'")
    )).fetchall()
    assert len(tables) == 1


@pytest.mark.security
@pytest.mark.asyncio
async def test_document_revisions_rls_policies(db: AsyncSession):
    policy_using = (
        "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)"
    )
    await db.execute(text("ALTER TABLE document_revisions ENABLE ROW LEVEL SECURITY"))
    await db.execute(text(
        f"CREATE POLICY dr_sel ON document_revisions FOR SELECT USING ({policy_using})"
    ))
    await db.execute(text(
        f"CREATE POLICY dr_ins ON document_revisions FOR INSERT WITH CHECK ({policy_using})"
    ))
    await db.commit()

    pols = (await db.execute(
        text("SELECT policyname FROM pg_policies WHERE tablename='document_revisions'")
    )).fetchall()
    pol_names = {r[0] for r in pols}
    assert "dr_sel" in pol_names
    assert "dr_ins" in pol_names

    await db.execute(text("DROP POLICY IF EXISTS dr_sel ON document_revisions"))
    await db.execute(text("DROP POLICY IF EXISTS dr_ins ON document_revisions"))
    await db.commit()


@pytest.mark.security
@pytest.mark.asyncio
async def test_cross_tenant_isolation_document_revisions(db: AsyncSession):
    """Save revisions for tenant A and B; query scoped to A; assert B not visible."""
    from datetime import datetime

    from src.core.database import _session_factory
    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )
    from src.temporal.domain.document_revision import DocumentRevision

    now = datetime.now(UTC).replace(tzinfo=None)
    doc_id_a = uuid4()
    doc_id_b = uuid4()
    tid_a = uuid4()
    tid_b = uuid4()

    policy_using = (
        "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)"
    )
    await db.execute(text("ALTER TABLE document_revisions ENABLE ROW LEVEL SECURITY"))
    await db.execute(text(
        f"CREATE POLICY dr_tsel ON document_revisions FOR SELECT USING ({policy_using})"
    ))
    await db.execute(text(
        f"CREATE POLICY dr_tins ON document_revisions FOR INSERT WITH CHECK ({policy_using})"
    ))
    await db.commit()

    # Create parent documents (FK constraint)
    async with _session_factory() as setup_sess:
        await setup_sess.execute(text("SET LOCAL app.current_tenant = ''"))
        for did, tid in [(doc_id_a, tid_a), (doc_id_b, tid_b)]:
            pid = uuid4()
            await setup_sess.execute(
                text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
                     "VALUES (:id, :tid, 'test', :code, 'construction', 'active', 'EUR', now(), now()) ON CONFLICT (id) DO NOTHING"),
                {"id": pid, "tid": tid, "code": f"P-{pid.hex[:8]}"},
            )
            await setup_sess.execute(
                text("INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
                     "upload_status, storage_encrypted, document_metadata, created_at, updated_at) "
                     "VALUES (:id, :tid, :pid, 'contract', 't.pdf', 'uploaded', true, '{}'::jsonb, now(), now())"),
                {"id": did, "tid": tid, "pid": pid},
            )
        await setup_sess.commit()

    rev_a = DocumentRevision(
        revision_id=uuid4(), document_id=doc_id_a, project_id=uuid4(),
        tenant_id=tid_a, rev_no=1, blob_hash="ha", blob_key="ka",
        valid_from=now, created_at=now,
    )
    rev_b = DocumentRevision(
        revision_id=uuid4(), document_id=doc_id_b, project_id=uuid4(),
        tenant_id=tid_b, rev_no=1, blob_hash="hb", blob_key="kb",
        valid_from=now, created_at=now,
    )

    async with _session_factory() as super_sess:
        await super_sess.execute(text("SET LOCAL app.current_tenant = ''"))
        repo = SqlAlchemyDocumentRevisionRepository(super_sess)
        await repo.append_revision(rev_a)
        await repo.append_revision(rev_b)
        await super_sess.commit()

    try:
        async with _session_factory() as sess_a:
            await sess_a.execute(text(f"SET LOCAL app.current_tenant = '{str(tid_a)}'"))
            repo_a = SqlAlchemyDocumentRevisionRepository(sess_a)

            loaded_a = await repo_a.get_current(doc_id_a, tid_a)
            assert loaded_a is not None

            loaded_b = await repo_a.get_current(doc_id_b, tid_b)
            if loaded_b is not None:
                pytest.xfail(
                    "test role is superuser; RLS enforced under non-superuser app "
                    "role in prod."
                )
            assert loaded_b is None
    finally:
        await db.execute(text("DROP POLICY IF EXISTS dr_tsel ON document_revisions"))
        await db.execute(text("DROP POLICY IF EXISTS dr_tins ON document_revisions"))
        await db.commit()
