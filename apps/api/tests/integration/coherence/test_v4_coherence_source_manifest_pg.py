"""Authenticate single-document Coherence calls inside a multi-document run.

Tests real tenant-scoped document_revisions; no LLM or fake cross-doc revision.
"""
from __future__ import annotations

import os
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.coherence.adapters.ai.coherence_governed_wrapper import (
    CoherenceEscrowIdentityError,
)
from src.coherence.adapters.ai.coherence_source_manifest import (
    CoherenceRevisionRef,
    verify_coherence_project_manifest,
)
from tests.integration.analysis.test_legacy_shared_reservations_pg import _seed

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="needs isolated migrated *_test postgres"),
]


async def _seed_second_doc(authority, project):
    doc, rev = uuid4(), uuid4()
    conn = await asyncpg.connect(_DSN)
    try:
        await conn.execute(
            "SELECT set_config('app.current_tenant', $1, false)",
            str(authority.tenant_id),
        )
        await conn.execute("""
            INSERT INTO public.documents
              (id, project_id, tenant_id, filename, document_type)
            VALUES ($1,$2,$3,'real-revision-seed.pdf','technical_spec')
        """, doc, project, authority.tenant_id)
        await conn.execute("""
            INSERT INTO public.document_revisions
              (revision_id,document_id,project_id,tenant_id,
               rev_no,blob_hash,blob_key,valid_from)
            VALUES ($1,$2,$3,$4,1,$5,'scratch/second',clock_timestamp())
        """, rev, doc, project, authority.tenant_id, "c" * 64)
    finally:
        await conn.close()
    return doc, rev


def _engine():
    return create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1),
    )


async def _manifest(
    engine, *, tenant, project, run_id, revisions,
    current=True, scoped=True,
):
    async with AsyncSession(engine) as session, session.begin():
        if scoped:
            await session.execute(
                text("SELECT set_config('app.current_tenant',:t,true)"),
                {"t": str(tenant)},
            )
        return await verify_coherence_project_manifest(
            session, tenant_id=tenant, project_id=project,
            run_id=run_id, revisions=tuple(revisions),
            require_current=current,
        )


async def test_two_real_revisions_are_pinned_and_bound_separately():
    a, project = await _seed()
    doc2, rev2 = await _seed_second_doc(a, project)
    run = uuid4()
    engine = _engine()
    try:
        r1 = CoherenceRevisionRef(a.document_id, a.revision_id)
        r2 = CoherenceRevisionRef(doc2, rev2)
        m1 = await _manifest(
            engine, tenant=a.tenant_id, project=project,
            run_id=run, revisions=(r1,r2),
        )
        m2 = await _manifest(
            engine, tenant=a.tenant_id, project=project,
            run_id=run, revisions=(r2,r1),
        )
        assert m1.manifest_sha256 == m2.manifest_sha256
        assert len(m1.members) == 2
        first = m1.bind_clause_source(
            document_id=a.document_id, revision_id=a.revision_id,
        )
        second = m1.bind_clause_source(document_id=doc2,revision_id=rev2)
        assert first.source_sha256 == "a" * 64
        assert second.source_sha256 == "c" * 64
        assert first.document_id != second.document_id
        k = {"rule_id": "R-1", "clause_id": "3.1",
             "clause_text":"A verified clause.", "rule_input_hash":"f"*64}
        assert first.request_key(**k) != second.request_key(**k)
        # A cross-document clause is not falsely assigned one revision.
        with pytest.raises(CoherenceEscrowIdentityError, match="cross-document"):
            m1.refuse_multi_source_clause(sources=(r1, r2))
        with pytest.raises(CoherenceEscrowIdentityError, match="not in"):
            m1.bind_clause_source(document_id=uuid4(),revision_id=uuid4())
    finally:
        await engine.dispose()


async def test_forged_tenant_project_and_revision_fail_closed():
    a, project = await _seed()
    engine = _engine()
    rev = CoherenceRevisionRef(a.document_id,a.revision_id)
    try:
        for tenant, candidate_project, sources in (
            (a.tenant_id,uuid4(),(rev,)),
            (a.tenant_id,project,(CoherenceRevisionRef(a.document_id,uuid4()),)),
        ):
            with pytest.raises(CoherenceEscrowIdentityError,match="not found"):
                await _manifest(
                    engine,tenant=tenant,project=candidate_project,
                    run_id=uuid4(),revisions=sources,
                )
        with pytest.raises(CoherenceEscrowIdentityError,match="tenant"):
            await _manifest(
                engine,tenant=a.tenant_id,project=project,
                run_id=uuid4(),revisions=(rev,),scoped=False,
            )
    finally:
        await engine.dispose()


async def test_same_document_two_revisions_rejected_not_aggregated():
    a, project = await _seed()
    engine = _engine()
    try:
        with pytest.raises(CoherenceEscrowIdentityError,match="one current"):
            await _manifest(
                engine,tenant=a.tenant_id,project=project,
                run_id=uuid4(),
                revisions=(
                    CoherenceRevisionRef(a.document_id,a.revision_id),
                    CoherenceRevisionRef(a.document_id,uuid4()),
                ),
            )
    finally:
        await engine.dispose()


async def test_stale_revision_fails_current_manifest():
    a, project = await _seed()
    conn = await asyncpg.connect(_DSN)
    try:
        await conn.execute(
            "SELECT set_config('app.current_tenant',$1,false)",
            str(a.tenant_id),
        )
        await conn.execute("""
            UPDATE public.document_revisions
               SET valid_to=clock_timestamp()
             WHERE revision_id=$1
        """,a.revision_id)
    finally:
        await conn.close()
    engine = _engine()
    try:
        with pytest.raises(CoherenceEscrowIdentityError,match="historical"):
            await _manifest(
                engine,tenant=a.tenant_id,project=project,
                run_id=uuid4(),
                revisions=(CoherenceRevisionRef(a.document_id,a.revision_id),),
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("bad", [(), (CoherenceRevisionRef(uuid4(),uuid4()),) * 2])
async def test_empty_or_duplicate_manifest_refused(bad):
    a, project = await _seed()
    engine = _engine()
    try:
        with pytest.raises(CoherenceEscrowIdentityError):
            await _manifest(
                engine,tenant=a.tenant_id,project=project,
                run_id=uuid4(),revisions=bad,
            )
    finally:
        await engine.dispose()
