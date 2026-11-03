"""S4 on real PostgreSQL: the exact original Budget row / Schedule activity a finding points at, or a refusal.

Before a cell is shown the reference is checked in the reader's tenant: document and revision exist and belong together,
the reference still names the stored bytes, the revision is still the document's current one, and the original bytes
still hash to the stored SHA-256. A stale, missing or foreign reference never returns content.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.http import structured_source_row_router as routes
from src.analysis.application.structured_source_row_view import (
    ImmutableStructuredRowFinder,
    ResolveStructuredSourceRowService,
)
from src.analysis.application.structured_source_trust import (
    StructuredTrustConflict,
    StructuredTrustNotFound,
)
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from tests.modules.integration.test_adr032_structured_source_trust_pg import (
    _approver,
    _decide,
    _document,
    _request,
    _reupload,
    _Storage,
    _world,
)

pytestmark = pytest.mark.asyncio


def _finder(storage: _Storage) -> ImmutableStructuredRowFinder:
    return ImmutableStructuredRowFinder(storage, ExcelFileParser())  # type: ignore[arg-type]


async def _resolve(factory, storage, w, doc, *, locator="Sheet!2", revision=None, tenant=None, expected="__doc__"):
    async with factory() as session:
        return await ResolveStructuredSourceRowService(session, _finder(storage)).execute(
            tenant_id=tenant or w["tenant"], document_id=doc["document"], revision_id=revision or doc["revision"],
            source_locator=locator, expected_blob_hash=doc["digest"] if expected == "__doc__" else expected,
        )


async def _budget_with_total(db: AsyncSession, w: dict, tmp_path: Path, storage: _Storage) -> dict:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Presupuesto"
    sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency", "Tax Basis", "WBS Node ID"])
    sheet.append(["Concrete foundation", 2, "m3", 120, 240, "EUR", "NET", str(w["node"])])
    sheet.append(["Total presupuesto", None, None, None, 1500000, "EUR", None, None])
    path = tmp_path / f"budget-total-{uuid4().hex[:6]}.xlsx"
    book.save(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document_id, revision_id = uuid4(), uuid4()
    key = f"synthetic/s4/{revision_id}.xlsx"
    storage.mapping[key] = path
    db.add(DocumentORM(
        id=document_id, tenant_id=w["tenant"], project_id=w["project"], document_type=DocumentType.BUDGET,
        filename="budget.xlsx", file_format=".xlsx", file_hash=digest, created_by=w["actor"],
    ))
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(DocumentRevisionORM(
        revision_id=revision_id, tenant_id=w["tenant"], project_id=w["project"], document_id=document_id, rev_no=1,
        blob_hash=digest, blob_key=key, valid_from=now, created_at=now,
    ))
    await db.commit()
    return {"family": "budget", "document": document_id, "revision": revision_id, "digest": digest, "path": path}


async def test_line_row_declared_total_and_schedule_activity_resolve_to_the_original_rows(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    budget = await _budget_with_total(db, w, tmp_path, storage)
    line = await _resolve(test_session_factory, storage, w, budget, locator="Presupuesto!2")
    assert line.family == "budget" and line.row["item"] == "Concrete foundation"
    assert line.blob_sha256 == budget["digest"] and line.rev_no == 1
    total = await _resolve(test_session_factory, storage, w, budget, locator="Presupuesto!3")
    assert total.row["kind"] == "declared_total" and total.row["total"] == 1500000
    schedule = await _document(db, w, tmp_path, storage, family="schedule")
    activity = await _resolve(test_session_factory, storage, w, schedule, locator="Sheet!2")
    assert activity.family == "schedule" and activity.row["source_activity_id"] == "ACT-100"


async def test_authority_is_reported_honestly_before_and_after_a_human_trusts_the_source(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    assert (await _resolve(test_session_factory, storage, w, doc)).authority == "UNTRUSTED_SINGLE_REVISION"
    receipt = await _request(test_session_factory, storage, w, doc)
    await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert (await _resolve(test_session_factory, storage, w, doc)).authority == "TRUSTED_CURRENT"


async def test_stale_foreign_and_missing_references_never_return_content(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    other = await _document(db, w, tmp_path, storage, family="schedule")
    # Another tenant: indistinguishable from a reference that does not exist.
    with pytest.raises(StructuredTrustNotFound):
        await _resolve(test_session_factory, storage, w, doc, tenant=uuid4())
    # Unknown revision; a revision that belongs to ANOTHER document; a document that is not a Budget/Schedule.
    with pytest.raises(StructuredTrustNotFound):
        await _resolve(test_session_factory, storage, w, doc, revision=uuid4())
    with pytest.raises(StructuredTrustNotFound):
        await _resolve(test_session_factory, storage, w, doc, revision=other["revision"])
    with pytest.raises(StructuredTrustNotFound):
        await _resolve(test_session_factory, storage, w, {**doc, "document": w["document"]}, revision=w["revision"])
    # The reference names bytes the revision does not hold.
    with pytest.raises(StructuredTrustConflict) as stale:
        await _resolve(test_session_factory, storage, w, doc, expected="0" * 64)
    assert stale.value.code == "stale_reference"
    # A locator the original does not have; and a locator that is not a row at all.
    for locator in ("Sheet!99", "not-a-locator"):
        with pytest.raises(StructuredTrustConflict) as missing:
            await _resolve(test_session_factory, storage, w, doc, locator=locator)
        assert missing.value.code == "source_unavailable"


async def test_a_superseded_revision_is_stale_and_tampered_bytes_are_refused(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _document(db, w, tmp_path, storage)
    await _reupload(db, w, tmp_path, storage, doc)
    with pytest.raises(StructuredTrustConflict) as old:
        await _resolve(test_session_factory, storage, w, doc)
    assert old.value.code == "stale_reference"
    tampered = await _document(db, w, tmp_path, storage, family="schedule")
    tampered["path"].write_bytes(tampered["path"].read_bytes() + b"tampered")
    with pytest.raises(StructuredTrustConflict) as altered:
        await _resolve(test_session_factory, storage, w, tampered)
    assert altered.value.code == "source_unavailable"


async def test_http_maps_the_outcomes_without_leaking_content(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    user = await db.get(User, w["actor"])
    assert user is not None
    doc = await _document(db, w, tmp_path, storage)
    monkeypatch.setattr(routes, "_finder", lambda: _finder(storage))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    base = f"/api/v1/documents/{doc['document']}/revisions/{doc['revision']}/structured-source-rows"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.get(base, params={"locator": "Sheet!2", "expected_blob_hash": doc["digest"]})
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["blob_sha256"] == doc["digest"] and body["source_assessment"] == "NOT_ASSESSED"
        assert body["row"]["item"] == "Concrete foundation" and body["authority"] == "UNTRUSTED_SINGLE_REVISION"
        stale = await client.get(base, params={"locator": "Sheet!2", "expected_blob_hash": "0" * 64})
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_reference"
        assert "row" not in stale.json() and "Concrete" not in stale.text
        assert (await client.get(base, params={"locator": "Sheet!99"})).status_code == 409
        assert (await client.get(base, params={"locator": "Sheet!2", "expected_blob_hash": "not-hex"})).status_code == 422
        assert (await client.get(base.replace(str(doc["revision"]), str(uuid4())), params={"locator": "Sheet!2"})).status_code == 404
    stranger = User(
        id=uuid4(), tenant_id=uuid4(), email=f"s4-{uuid4().hex}@example.invalid",
        clerk_user_id=f"s4-{uuid4().hex}", is_active=True, is_verified=False,
    )
    app.dependency_overrides[get_current_user] = lambda: stranger
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get(base, params={"locator": "Sheet!2"})
        assert denied.status_code == 404 and "Concrete" not in denied.text
