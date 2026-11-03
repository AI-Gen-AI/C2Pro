"""S4 (Schedule): a REAL schedule activity originates a verifiable, navigable reference -- only when a finding exists.

Nothing here is synthetic between the file and the alert: a real ``.xlsx`` schedule is read by the worker's own
extractor (``extract_schedule_planned_finish``), the observation is stored on the document, the real loader accepts it
only for the document's current revision, the production assembly + comparator produce the PROVISIONAL deviation, the
production alert mapping stores the pointer, and the verifying endpoint returns the exact activity row from the stored
bytes. A project whose schedule meets the contractual deadline produces no finding and therefore no pointer: no alert is
invented to have something to link.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import openpyxl
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.application.dtos import DetectionEvidenceResponse
from src.analysis.adapters.http import structured_source_row_router as routes
from src.analysis.application.structured_source_trust import (
    StructuredTrustConflict,
    StructuredTrustNotFound,
)
from src.coherence.cross_document import cross_document_assessment
from src.coherence.cross_document.inputs import DATE_KIND_CONTRACT_COMPLETION
from src.coherence.graph.nodes import _provisional_deviation_alert
from src.coherence.models import Clause, structured_source_refs
from src.coherence.router import _coherence_alert_to_create
from src.coherence.schedule_clause_builder import load_schedule_planned_finish
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.application.schedule_planned_finish import (
    METADATA_KEY,
    extract_schedule_planned_finish,
)
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from tests.modules.integration.test_adr032_structured_source_trust_pg import _Storage, _world
from tests.modules.integration.test_s4_structured_source_row_pg import _resolve

pytestmark = pytest.mark.asyncio

DEADLINE = "2027-06-30"
ACTIVITIES = [  # (task, start, end, id) -- ACT-300 (sheet row 4) is the LATEST finish
    ("Foundations", "2027-01-04", "2027-03-01", "ACT-100"),
    ("Structure", "2027-03-02", "2027-05-15", "ACT-200"),
    ("Fit-out and handover", "2027-05-16", "2027-09-30", "ACT-300"),
]
MEETS_DEADLINE = [(t, s, "2027-06-15" if i == 2 else e, a) for i, (t, s, e, a) in enumerate(ACTIVITIES)]


def _workbook(path: Path, activities: list[tuple[str, str, str, str]], node: UUID) -> str:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Task", "Start Date", "End Date", "Duration", "Activity ID", "WBS Node ID"])
    for task, start, end, activity in activities:
        sheet.append([task, start, end, 30, activity, str(node)])
    book.save(path)
    book.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _schedule(db: AsyncSession, w: dict, tmp_path: Path, storage: _Storage, activities) -> dict:
    path = tmp_path / f"schedule-{uuid4().hex[:6]}.xlsx"
    digest = _workbook(path, activities, w["node"])
    document_id, revision_id = uuid4(), uuid4()
    key = f"synthetic/s4-schedule/{revision_id}.xlsx"
    storage.mapping[key] = path
    db.add(DocumentORM(
        id=document_id, tenant_id=w["tenant"], project_id=w["project"], document_type=DocumentType.SCHEDULE,
        filename="schedule.xlsx", file_format=".xlsx", file_hash=digest, created_by=w["actor"],
    ))
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(DocumentRevisionORM(
        revision_id=revision_id, tenant_id=w["tenant"], project_id=w["project"], document_id=document_id, rev_no=1,
        blob_hash=digest, blob_key=key, valid_from=now, created_at=now,
    ))
    await db.commit()
    return {"family": "schedule", "document": document_id, "revision": revision_id, "digest": digest, "path": path}


async def _observe(db: AsyncSession, doc: dict) -> dict:
    """What the ingestion worker does for a schedule: re-read the pinned bytes and store the observation."""
    observation = await extract_schedule_planned_finish(
        ExcelFileParser(), file_path=doc["path"], file_format=".xlsx", document_id=doc["document"],
        revision_id=doc["revision"], blob_hash=doc["digest"],
    )
    await db.execute(
        update(DocumentORM).where(DocumentORM.id == doc["document"]).values(document_metadata={METADATA_KEY: observation})
    )
    await db.commit()
    return observation


def _contract(document_id: UUID, revision_id: UUID) -> list[Clause]:
    return [Clause(
        id="clause-17", text="El plazo de ejecucion finaliza el 30 de junio de 2027.",
        data={
            "document_id": str(document_id),
            "completion_deadline": {"date": DEADLINE, "kind": DATE_KIND_CONTRACT_COMPLETION},
            "evidence_location": {"revision_id": str(revision_id)},
        },
    )]


async def test_a_real_activity_originates_a_pointer_that_the_endpoint_verifies_against_the_stored_bytes(
    db: AsyncSession, test_session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _schedule(db, w, tmp_path, storage, ACTIVITIES)

    observation = await _observe(db, doc)
    assert observation["date"] == "2027-09-30" and observation["source_locator"] == "Sheet!4"
    assert observation["activity"] == "Fit-out and handover"

    loaded = await load_schedule_planned_finish(db, w["project"], w["tenant"])
    assert loaded is not None and loaded["revision_id"] == str(doc["revision"]), "accepted for the CURRENT revision"

    clauses = _contract(uuid4(), uuid4())
    [provisional] = cross_document_assessment(clauses, schedule_planned_finish=loaded).provisional
    alert = _provisional_deviation_alert(
        SimpleNamespace(evidence=provisional.evidence, source_clause_id=provisional.source_clause_id, delta=provisional.delta),
        clauses,
    )
    create = _coherence_alert_to_create(project_id=w["project"], alert=alert, clauses=clauses, persisted_clause_documents={})
    stored = create.alert_metadata["detection_evidence"]["structured_sources"]
    [ref] = structured_source_refs(stored)
    assert (ref.family, str(ref.document_id), str(ref.revision_id), ref.source_locator) == (
        "schedule", str(doc["document"]), str(doc["revision"]), "Sheet!4",
    )
    shown = DetectionEvidenceResponse(**create.alert_metadata["detection_evidence"])
    assert shown.structured_sources[0].source_locator == "Sheet!4", "the alert API exposes it for navigation"

    # The pointer opens the EXACT activity row, re-read from the stored bytes, under the observed SHA-256.
    row = await _resolve(
        test_session_factory, storage, w, doc, locator=ref.source_locator, expected=ref.blob_sha256 or doc["digest"]
    )
    assert row.family == "schedule" and row.blob_sha256 == doc["digest"]
    assert row.row["source_activity_id"] == "ACT-300" and row.row["task"] == "Fit-out and handover"
    assert str(row.row["end_date"]).startswith("2027-09-30")
    assert row.authority == "UNTRUSTED_SINGLE_REVISION", "an untrusted schedule is reported as such, never as trusted"

    user = await db.get(User, w["actor"])
    assert user is not None
    monkeypatch.setattr(routes, "_finder", lambda: __import__(
        "tests.modules.integration.test_s4_structured_source_row_pg", fromlist=["_finder"])._finder(storage))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    url = f"/api/v1/documents/{doc['document']}/revisions/{doc['revision']}/structured-source-rows"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.get(url, params={"locator": ref.source_locator, "expected_blob_hash": doc["digest"]})
        assert ok.status_code == 200 and ok.json()["row"]["source_activity_id"] == "ACT-300"


async def test_a_replaced_revision_or_a_foreign_tenant_never_gets_the_activity(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    from tests.modules.integration.test_adr032_structured_source_trust_pg import _reupload

    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _schedule(db, w, tmp_path, storage, ACTIVITIES)
    await _observe(db, doc)

    # Another tenant: indistinguishable from a reference that does not exist.
    with pytest.raises(StructuredTrustNotFound):
        await _resolve(test_session_factory, storage, w, doc, locator="Sheet!4", tenant=uuid4())

    # The pointer's own bytes changed (SHA mismatch) -> refused without content.
    with pytest.raises(StructuredTrustConflict) as other_bytes:
        await _resolve(test_session_factory, storage, w, doc, locator="Sheet!4", expected="0" * 64)
    assert other_bytes.value.code == "stale_reference"

    # A re-upload supersedes the revision: the old pointer is stale, AND the stale observation produces no finding.
    await _reupload(db, w, tmp_path, storage, doc)
    with pytest.raises(StructuredTrustConflict) as superseded:
        await _resolve(test_session_factory, storage, w, doc, locator="Sheet!4")
    assert superseded.value.code == "stale_reference"
    loaded = await load_schedule_planned_finish(db, w["project"], w["tenant"])
    assert loaded is not None and loaded["reason"] == "schedule_revision_not_current"
    assessment = cross_document_assessment(_contract(uuid4(), uuid4()), schedule_planned_finish=loaded)
    assert assessment.provisional == [], "a stale observation never becomes a finding"


async def test_a_schedule_that_meets_the_deadline_yields_no_finding_and_therefore_no_pointer(
    db: AsyncSession, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    doc = await _schedule(db, w, tmp_path, storage, MEETS_DEADLINE)
    observation = await _observe(db, doc)
    assert observation["date"] == "2027-06-15"

    loaded = await load_schedule_planned_finish(db, w["project"], w["tenant"])
    assessment = cross_document_assessment(_contract(uuid4(), uuid4()), schedule_planned_finish=loaded)
    assert assessment.provisional == [] and assessment.findings == [], "no overrun -> nothing to point at"
