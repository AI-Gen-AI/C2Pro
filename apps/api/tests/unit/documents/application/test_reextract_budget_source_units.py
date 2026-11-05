"""Controlled re-extraction of an analysed budget revision's original XLSX rows (real parser)."""

from __future__ import annotations

import hashlib
import json
import shutil
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openpyxl import Workbook

from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.application.reextract_budget_source_units import (
    BudgetReextractionError,
    reextract_budget_source_units,
)
from src.documents.domain.models import DocumentStatus, DocumentType


class _Result:
    def __init__(self, rows=(), scalar=None):
        self._rows, self._scalar = list(rows), scalar

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar


class _Savepoint:
    def __init__(self, session):
        self._session, self._snapshot = session, dict(session.units)

    async def rollback(self):
        self._session.units = dict(self._snapshot)

    async def commit(self):
        return None


class _FakeSession:
    """In-memory stand-in for document_source_units keyed by source_locator."""

    def __init__(self, status=DocumentStatus.ANALYZED.value):
        self.units: dict[str, str] = {}
        self.status = status
        self.commits = 0
        self.rollbacks = 0

    async def begin_nested(self):
        return _Savepoint(self)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "DELETE FROM public.document_source_units" in sql:
            self.units = {}
        elif "INSERT INTO public.document_source_units" in sql:
            for row in params if isinstance(params, list) else [params]:
                self.units[row["source_locator"]] = row["unit_sha256"]
        elif "SELECT source_locator, unit_sha256" in sql:
            return _Result(self.units.items())
        elif "SELECT upload_status" in sql:
            return _Result(scalar=self.status)
        return _Result()


def _workbook(path, *, with_total=True):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Budget"
    sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency"])
    sheet.append(["Transformer", 1, "unit", 600000, 600000, "EUR"])
    sheet.append(["Erection and commissioning", 1, "lot", 500000, 500000, "EUR"])
    sheet.append(["Contingency", 1, "lot", 200000, 200000, "EUR"])
    if with_total:
        sheet.append(["TOTAL BUDGET", None, None, None, 1300000, "EUR"])
    workbook.save(path)


def _scenario(tmp_path, *, status=DocumentStatus.ANALYZED.value):
    source = tmp_path / "source.xlsx"
    _workbook(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    tenant_id, project_id, document_id, revision_id = (uuid4() for _ in range(4))
    revision = SimpleNamespace(
        revision_id=revision_id, blob_key="rev/source.xlsx", blob_hash=digest
    )
    document = SimpleNamespace(
        id=document_id,
        project_id=project_id,
        document_type=DocumentType.BUDGET,
        file_format=".xlsx",
        filename="03_Presupuesto_EPC.xlsx",
        upload_status=DocumentStatus.ANALYZED,
        document_metadata={
            "analysis_marker": "keep-me",
            "source_units_by_revision": {str(revision_id): {"units": 3}},
        },
    )
    session = _FakeSession(status)
    # State left by the previous (pre-fix) extraction: three lines, no declared total.
    session.units = {"Budget!2": "old2", "Budget!3": "old3", "Budget!4": "old4"}

    async def download_object(_key):
        copy = tmp_path / f"download-{uuid4().hex}.xlsx"
        shutil.copy(source, copy)
        return copy

    metadata_writes: list[dict] = []

    async def update_metadata(_tenant, _document, metadata):
        metadata_writes.append(metadata)

    deps = {
        "session": session,
        "document_repository": SimpleNamespace(
            get_by_id=_async(lambda *_a: document), update_metadata=update_metadata
        ),
        "revision_repository": SimpleNamespace(
            lock_lineage=_async(lambda *_a: None),
            get_current=_async(lambda *_a: revision),
        ),
        "storage": SimpleNamespace(download_object=download_object),
        "file_parser": CompositeFileParser(
            bc3_parser=BC3FileParser(), excel_parser=ExcelFileParser(), pdf_parser=PDFFileParser()
        ),
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id": document_id,
        "expected_revision_id": revision_id,
        "expected_blob_hash": digest,
    }
    return deps, session, revision, document, metadata_writes


def _async(fn):
    async def call(*args, **kwargs):
        return fn(*args, **kwargs)

    return call


@pytest.mark.asyncio
async def test_reextraction_recovers_declared_total_and_is_idempotent(tmp_path):
    deps, session, revision, document, writes = _scenario(tmp_path)

    first = await reextract_budget_source_units(**deps)

    assert first["revision_id"] == str(revision.revision_id)
    assert first["blob_hash"] == revision.blob_hash
    assert first["units_before"] == 3 and first["units_after"] == 4
    assert first["added_locators"] == ["Budget!5"]
    assert sorted(session.units) == ["Budget!2", "Budget!3", "Budget!4", "Budget!5"]
    assert session.commits == 1
    metadata = writes[-1]
    assert metadata["analysis_marker"] == "keep-me"  # unrelated metadata preserved
    entry = metadata["stated_total_by_revision"][str(revision.revision_id)]
    assert entry["total"] == 1300000
    assert entry["currencies"] == ["EUR"]
    assert entry["source_locator"] == "Budget!5"
    assert entry["blob_hash"] == revision.blob_hash
    assert metadata["source_units_by_revision"][str(revision.revision_id)]["units"] == 4

    # Second identical attempt: same evidence, no row churn, no metadata write.
    document.document_metadata = metadata
    writes.clear()
    stable_digests = dict(session.units)
    second = await reextract_budget_source_units(**deps)
    assert second["changed"] is False
    assert second["added_locators"] == second["removed_locators"] == []
    assert session.units == stable_digests
    assert writes == []
    assert json.dumps(sorted(session.units)) == json.dumps(sorted(stable_digests))


@pytest.mark.asyncio
async def test_reextraction_fails_closed_on_hash_cas_tampered_bytes_or_state(tmp_path):
    deps, session, _revision, _document, writes = _scenario(tmp_path)
    before = dict(session.units)

    with pytest.raises(BudgetReextractionError) as stale:
        await reextract_budget_source_units(**{**deps, "expected_blob_hash": "0" * 64})
    assert stale.value.code == "REVISION_HASH_PRECONDITION_FAILED"

    with pytest.raises(BudgetReextractionError) as other_revision:
        await reextract_budget_source_units(**{**deps, "expected_revision_id": uuid4()})
    assert other_revision.value.code == "REVISION_NOT_CURRENT"

    async def tampered(_key):
        path = tmp_path / "tampered.xlsx"
        _workbook(path, with_total=False)
        return path

    deps["storage"] = SimpleNamespace(download_object=tampered)
    with pytest.raises(BudgetReextractionError) as mismatch:
        await reextract_budget_source_units(**deps)
    assert mismatch.value.code.startswith("REVISION_SOURCE_INVALID")

    busy_deps, busy_session, *_ = _scenario(tmp_path, status=DocumentStatus.PARSING.value)
    with pytest.raises(BudgetReextractionError) as busy:
        await reextract_budget_source_units(**busy_deps)
    assert busy.value.code == "DOCUMENT_STATE_NOT_REEXTRACTABLE"

    assert session.units == before and writes == [] and session.commits == 0
    assert busy_session.commits == 0
