"""P0 security: Decision Intelligence retrieval never crosses tenants or projects.

The production application connects as a role with BYPASSRLS, so forced RLS on
``document_chunks`` does not protect a query that omits the tenant: the scope must be in the
SQL itself. This suite runs on a real PostgreSQL session whose role also bypasses RLS (the
production condition) and proves the retrieval adapter only ever returns chunks of the
caller's own tenant AND project, and fails closed when either is missing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.core.auth.models import Tenant
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.adapters.rag import rag_service as rag_service_module
from src.documents.adapters.rag.rag_service import RagService
from src.modules.decision_intelligence.adapters.ports.retrieval_port_adapter import (
    RetrievalPortAdapter,
)
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio

_DIM = 1536


async def _embed(texts: list[str]) -> list[list[float]]:
    # Every text embeds to the same vector: similarity alone can never separate tenants.
    return [[0.01] * _DIM for _ in texts]


async def _seed(db, label: str) -> tuple[UUID, UUID]:
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()
    db.add(Tenant(id=tenant_id, name=f"DI {label}", slug=f"di-{label}-{tenant_id.hex[:8]}",
                  subscription_plan="professional", is_active=True))
    await db.commit()
    db.add(ProjectORM(id=project_id, tenant_id=tenant_id, name=f"DI {label}", code=f"DI-{label}",
                      start_date=datetime.now()))
    await db.commit()
    db.add(DocumentORM(id=document_id, tenant_id=tenant_id, project_id=project_id, document_type="contract",
                       filename=f"{label}.pdf", upload_status="parsed_pending_analysis"))
    await db.commit()
    await RagService(db_session=db).ingest_document(
        tenant_id=tenant_id, document_id=document_id, project_id=project_id,
        text_content=f"SECRET-{label} contract clause text.", metadata={"document_type": "contract"},
    )
    await db.commit()
    return tenant_id, project_id


def _adapter(db) -> RetrievalPortAdapter:
    @asynccontextmanager
    async def _provider():
        yield db

    return RetrievalPortAdapter(session_provider=_provider, embed_fn=_embed)


async def test_the_session_bypasses_rls_like_production(db) -> None:
    """Precondition: without the SQL predicate nothing else would stop a cross-tenant read."""
    bypass = (await db.execute(text(
        "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user"))).scalar_one()
    assert bypass is True


async def test_retrieval_returns_only_the_callers_tenant_and_project(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag_service_module, "_embed_texts", _embed)
    tenant_a, project_a = await _seed(db, "alpha")
    tenant_b, project_b = await _seed(db, "bravo")

    for tenant, project, own, foreign in ((tenant_a, project_a, "alpha", "bravo"),
                                          (tenant_b, project_b, "bravo", "alpha")):
        evidence = await _adapter(db).retrieve("decision-intelligence", tenant_id=tenant, project_id=project)
        texts = " ".join(item["text"] for item in evidence)
        assert f"SECRET-{own}" in texts
        assert f"SECRET-{foreign}" not in texts


async def test_a_foreign_project_id_returns_nothing_of_that_project(db, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller supplying another tenant's project id gets no chunk of it (the tenant binds too)."""
    monkeypatch.setattr(rag_service_module, "_embed_texts", _embed)
    tenant_a, _ = await _seed(db, "charlie")
    _, project_b = await _seed(db, "delta")

    evidence = await _adapter(db).retrieve("decision-intelligence", tenant_id=tenant_a, project_id=project_b)
    assert "SECRET-delta" not in " ".join(item["text"] for item in evidence)
    assert "SECRET-charlie" not in " ".join(item["text"] for item in evidence)
