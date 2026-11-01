"""S4: a finding that rests on a Budget row / Schedule activity carries a pointer to that ORIGINAL row.

The chain is deterministic end to end -- parser -> revision declaration -> budget clause -> cross-document inputs ->
comparator evidence -> signal -> alert -> detection evidence -> API -- and a pointer is built only from what the parser
observed in an immutable revision. Anything malformed is dropped, never repaired or invented from text.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import openpyxl
import pytest

from src.alerts.application.dtos import DetectionEvidenceResponse
from src.coherence.budget_clause_builder import build_budget_clauses
from src.coherence.cross_document import assemble_cross_doc_inputs, assess_numeric_comparators
from src.coherence.cross_document.comparators import schedule_overruns_deadline
from src.coherence.cross_document.inputs import (
    BASIS_SOURCE_OBSERVED,
    DATE_KIND_CONTRACT_COMPLETION,
    DATE_KIND_SCHEDULE_FINISH,
    DatedSource,
    ProjectCrossDocInputs,
)
from src.coherence.cross_document.signal_adapter import to_finding_signal
from src.coherence.graph.nodes import _provisional_deviation_alert, _signal_to_alert
from src.coherence.models import Clause, structured_source_refs
from src.coherence.router import _coherence_alert_to_create
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.application.budget_stated_total import record_revision_stated_total

DOC, REV, SHA = str(uuid4()), str(uuid4()), "c" * 64
BUDGET_SOURCE = {"family": "budget", "document_id": DOC, "revision_id": REV, "blob_sha256": SHA, "source_locator": "Presupuesto!3"}


def _budget_workbook(path: Path) -> Path:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Presupuesto"
    sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency", "Tax Basis", "WBS Node ID"])
    sheet.append(["Concrete foundation", 2, "m3", 120, 240, "EUR", "NET", None])
    sheet.append(["Total presupuesto", None, None, None, 1500000, "EUR", None, None])
    book.save(path)
    return path


@pytest.mark.asyncio
async def test_the_parser_reports_where_the_declared_total_sits(tmp_path: Path) -> None:
    path = _budget_workbook(tmp_path / "b.xlsx")
    for evidence in (False, True):
        rows = await ExcelFileParser().parse_budget(path, include_evidence=evidence)
        assert rows.stated_total == 1500000
        assert rows.stated_total_locator == "Presupuesto!3"
        assert rows.declared_total_rows == [
            {"source_locator": "Presupuesto!3", "kind": "declared_total", "item": "Total presupuesto",
             "total": 1500000, "currency": "EUR"}
        ]
        # The declared-total row is not a line item: the rows themselves are unchanged.
        assert [r.get("source_locator") for r in rows if evidence] in ([], ["Presupuesto!2"])


def test_the_revision_declaration_keeps_the_locator_only_with_a_total() -> None:
    meta: dict = {}
    record_revision_stated_total(meta, revision_id=REV, blob_hash=SHA, total=10, currencies=["EUR"], source_locator="S!3")
    assert meta["stated_total_by_revision"][REV]["source_locator"] == "S!3"
    other: dict = {}
    record_revision_stated_total(other, revision_id=REV, blob_hash=SHA, total=None, currencies=None, source_locator="S!3")
    assert other["stated_total_by_revision"][REV]["source_locator"] is None


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt, _params):
        return self._results.pop(0) if self._results else _Result([])


@pytest.mark.asyncio
async def test_the_budget_clause_carries_the_source_row_only_when_one_was_observed() -> None:
    with_source = _Session([_Result([(1_500_000, ["EUR"], uuid4() if False else DOC, REV, SHA, "Presupuesto!3")])])
    [clause] = await build_budget_clauses(with_source, uuid4(), uuid4())  # type: ignore[arg-type]
    assert clause.data["stated_total_source"] == {
        "family": "budget", "document_id": DOC, "revision_id": REV, "blob_sha256": SHA, "source_locator": "Presupuesto!3"
    }
    without = _Session([_Result([(1_500_000, ["EUR"], DOC, REV, SHA, None)])])
    [bare] = await build_budget_clauses(without, uuid4(), uuid4())  # type: ignore[arg-type]
    assert "stated_total_source" not in bare.data
    legacy = _Session([_Result([(1_500_000, ["EUR"])])])
    [old] = await build_budget_clauses(legacy, uuid4(), uuid4())  # type: ignore[arg-type]
    assert "stated_total_source" not in old.data


def _inputs(source=BUDGET_SOURCE, budget=1_500_000.0, contract=1_000_000.0) -> ProjectCrossDocInputs:
    clauses = [
        Clause(id="c", text="contract", data={"contract_total": contract}),
        Clause(id="b", text="budget", data={"stated_total": budget, **({"stated_total_source": source} if source else {})}),
    ]
    return assemble_cross_doc_inputs(clauses)


def test_assembly_takes_the_source_of_the_clause_that_supplied_the_figure() -> None:
    assert dict(_inputs().budget_total_source or {}) == BUDGET_SOURCE
    assert _inputs(source=None).budget_total_source is None
    # A malformed source is not a source.
    assert _inputs(source={"family": "budget", "document_id": DOC}).budget_total_source is None
    # The larger figure wins, together with ITS source.
    clauses = [
        Clause(id="c", text="contract", data={"contract_total": 1.0}),
        Clause(id="b1", text="b1", data={"stated_total": 10.0, "stated_total_source": {**BUDGET_SOURCE, "source_locator": "P!2"}}),
        Clause(id="b2", text="b2", data={"stated_total": 99.0, "stated_total_source": {**BUDGET_SOURCE, "source_locator": "P!9"}}),
    ]
    assert dict(assemble_cross_doc_inputs(clauses).budget_total_source or {})["source_locator"] == "P!9"


def test_total_level_findings_point_at_the_original_budget_row_through_to_the_alert() -> None:
    assessment = assess_numeric_comparators(_inputs())
    findings = {f.rule_id: f for f in assessment.findings}
    assert {"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"} <= set(findings)
    for rule in ("DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"):
        assert findings[rule].evidence["sources"] == [BUDGET_SOURCE]
        alert = _signal_to_alert(to_finding_signal(findings[rule]))
        [ref] = alert.evidence.structured_sources
        assert (ref.family, ref.document_id, ref.revision_id, ref.source_locator, ref.blob_sha256) == (
            "budget", DOC, REV, "Presupuesto!3", SHA
        )
        create = _coherence_alert_to_create(
            project_id=uuid4(), alert=alert, clauses=[], persisted_clause_documents={}
        )
        stored = create.alert_metadata["detection_evidence"]["structured_sources"]
        assert stored == [ref.model_dump(mode="json")]
        shown = DetectionEvidenceResponse(**create.alert_metadata["detection_evidence"])
        assert shown.structured_sources[0].source_locator == "Presupuesto!3"


def test_without_an_observed_source_the_alert_points_at_nothing() -> None:
    alert = _signal_to_alert(to_finding_signal({f.rule_id: f for f in assess_numeric_comparators(_inputs(source=None)).findings}["DET-CRS-CONBUD"]))
    assert alert.evidence.structured_sources == []
    create = _coherence_alert_to_create(project_id=uuid4(), alert=alert, clauses=[], persisted_clause_documents={})
    assert "structured_sources" not in create.alert_metadata["detection_evidence"]


def test_a_pointer_is_never_invented_or_repaired_from_loose_data() -> None:
    good = {"family": "schedule", "document_id": DOC, "revision_id": REV, "source_locator": "Plan!4"}
    refs = structured_source_refs(
        [
            good,
            good,  # duplicate
            {"family": "contract", "document_id": DOC, "revision_id": REV, "source_locator": "x"},  # not structured
            {"family": "budget", "document_id": DOC, "revision_id": REV},  # no locator
            {"family": "budget", "revision_id": REV, "source_locator": "P!2"},  # no document
            "Plan!4",  # free text
            None,
        ]
    )
    assert [r.source_locator for r in refs] == ["Plan!4"]
    assert structured_source_refs("not a list") == [] and structured_source_refs(None) == []


def test_the_schedule_deviation_points_at_the_original_activity_row() -> None:
    inputs = ProjectCrossDocInputs(
        contract_completion=DatedSource(
            kind=DATE_KIND_CONTRACT_COMPLETION, value="2027-06-30", document_id=str(uuid4()),
            revision_id=str(uuid4()), locator=str(uuid4()),
        ),
        schedule_finish=DatedSource(
            kind=DATE_KIND_SCHEDULE_FINISH, value="2027-09-30", document_id=DOC, revision_id=REV,
            locator="Plan!4", basis=BASIS_SOURCE_OBSERVED,
        ),
    )
    provisional = schedule_overruns_deadline(inputs)
    assert provisional is not None and provisional.evidence["sources"] == [
        {"family": "schedule", "document_id": DOC, "revision_id": REV, "source_locator": "Plan!4"}
    ]
    clause_id = provisional.source_clause_id
    alert = _provisional_deviation_alert(
        SimpleNamespace(evidence=provisional.evidence, source_clause_id=clause_id, delta=provisional.delta),
        [Clause(id=str(clause_id), text="Plazo. La fecha de finalización será el 30 de junio de 2027.", data={})],
    )
    [ref] = alert.evidence.structured_sources
    assert (ref.family, ref.document_id, ref.revision_id, ref.source_locator) == ("schedule", DOC, REV, "Plan!4")
