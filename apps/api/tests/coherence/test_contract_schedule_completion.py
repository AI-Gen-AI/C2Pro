"""Contract completion deadline vs schedule planned finish (DET-CRS-SCHDEAD, TIME).

Refers to Suite ID: TS-UD-COH-XDOC-SCHDEAD-001.

A finding needs two SOURCED, COMPARABLE, calendar-exact dates whose order is violated. Anything
else is NOT_ASSESSED with its reason -- never a fabricated discrepancy.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

from src.coherence.cross_document import (
    DATE_KIND_CONTRACT_COMPLETION,
    DATE_KIND_SCHEDULE_FINISH,
    CrossDocFinding,
    CrossDocNotAssessed,
    DatedSource,
    ProjectCrossDocInputs,
    assemble_cross_doc_inputs,
    cross_document_signals,
    schedule_overruns_deadline,
)
from src.coherence.cross_document.comparators import assess_numeric_comparators
from src.coherence.models import Clause
from src.core.tasks.ingestion_tasks import _extract_contract_completion_deadline
from src.documents.application.schedule_planned_finish import summarize_schedule_planned_finish

DOC_C, REV_C, DOC_S, REV_S = (str(uuid4()) for _ in range(4))


def _contract(value: str | None = "2027-06-30", **overrides: object) -> DatedSource:
    base: dict[str, object] = {
        "kind": DATE_KIND_CONTRACT_COMPLETION,
        "value": value,
        "document_id": DOC_C,
        "revision_id": REV_C,
        "locator": "clause-17",
    }
    return DatedSource(**{**base, **overrides})  # type: ignore[arg-type]


def _schedule(value: str | None = "2027-09-30", **overrides: object) -> DatedSource:
    base: dict[str, object] = {
        "kind": DATE_KIND_SCHEDULE_FINISH,
        "value": value,
        "document_id": DOC_S,
        "revision_id": REV_S,
        "locator": "Plan!42",
    }
    return DatedSource(**{**base, **overrides})  # type: ignore[arg-type]


def _inputs(contract: DatedSource | None, schedule: DatedSource | None) -> ProjectCrossDocInputs:
    return ProjectCrossDocInputs(contract_completion=contract, schedule_finish=schedule)


# ── comparator: finding ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_schedule_after_contract_completion_is_a_sourced_time_finding() -> None:
    finding = schedule_overruns_deadline(_inputs(_contract(), _schedule()))

    assert isinstance(finding, CrossDocFinding)
    assert (finding.rule_id, finding.category) == ("DET-CRS-SCHDEAD", "TIME")
    assert finding.delta == (date(2027, 9, 30) - date(2027, 6, 30)).days
    assert finding.source_clause_id == "clause-17"
    assert finding.evidence["expected"] == {
        "kind": DATE_KIND_CONTRACT_COMPLETION,
        "date": "2027-06-30",
        "document_id": DOC_C,
        "revision_id": REV_C,
        "clause_id": "clause-17",
    }
    assert finding.evidence["observed"] == {
        "kind": DATE_KIND_SCHEDULE_FINISH,
        "date": "2027-09-30",
        "document_id": DOC_S,
        "revision_id": REV_S,
        "source_locator": "Plan!42",
    }


@pytest.mark.unit
@pytest.mark.parametrize("schedule_end", ["2027-06-30", "2027-05-01"])
def test_schedule_on_or_before_completion_is_not_a_finding(schedule_end: str) -> None:
    assert schedule_overruns_deadline(_inputs(_contract(), _schedule(schedule_end))) is None


@pytest.mark.unit
def test_an_absent_side_has_nothing_to_compare() -> None:
    assert schedule_overruns_deadline(_inputs(_contract(), None)) is None
    assert schedule_overruns_deadline(_inputs(None, _schedule())) is None
    assert schedule_overruns_deadline(ProjectCrossDocInputs()) is None


# ── comparator: NOT_ASSESSED, never a finding ─────────────────────────────────


def _not_assessed(contract: DatedSource, schedule: DatedSource) -> CrossDocNotAssessed:
    outcome = schedule_overruns_deadline(_inputs(contract, schedule))
    assert isinstance(outcome, CrossDocNotAssessed)
    assert outcome.state == "NOT_ASSESSED"
    assert outcome.rule_id == "DET-CRS-SCHDEAD"
    return outcome


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["MILESTONE", "CONTRACT_DURATION", "START_DATE"])
def test_a_contract_date_that_is_not_a_completion_deadline_is_not_comparable(kind: str) -> None:
    assert _not_assessed(_contract(kind=kind), _schedule()).reason == "DATE_KIND_NOT_COMPARABLE"


@pytest.mark.unit
def test_a_schedule_date_that_is_not_the_planned_finish_is_not_comparable() -> None:
    assert _not_assessed(_contract(), _schedule(kind="MILESTONE")).reason == (
        "DATE_KIND_NOT_COMPARABLE"
    )


@pytest.mark.unit
@pytest.mark.parametrize("missing", ["document_id", "revision_id", "locator"])
def test_a_date_without_a_verifiable_source_is_not_assessed(missing: str) -> None:
    assert _not_assessed(_contract(**{missing: None}), _schedule()).reason == "UNSOURCED_DATE"
    assert _not_assessed(_contract(), _schedule(**{missing: None})).reason == "UNSOURCED_DATE"


@pytest.mark.unit
def test_a_source_without_an_assessable_date_reports_its_reason() -> None:
    outcome = _not_assessed(_contract(), _schedule(None, reason="no_row_with_unambiguous_start_and_end"))
    assert outcome.reason == "DATE_NOT_ASSESSED"
    assert "no_row_with_unambiguous_start_and_end" in outcome.detail


@pytest.mark.unit
@pytest.mark.parametrize("ambiguous", ["05/06/2027", "2027-13-40", "30 June 2027", "2027-06-30T10:00"])
def test_a_date_that_is_not_an_iso_calendar_date_is_ambiguous(ambiguous: str) -> None:
    assert _not_assessed(_contract(ambiguous), _schedule()).reason == "AMBIGUOUS_DATE"
    assert _not_assessed(_contract(), _schedule(ambiguous)).reason == "AMBIGUOUS_DATE"


@pytest.mark.unit
def test_not_assessed_dates_are_reported_but_never_become_findings() -> None:
    assessment = assess_numeric_comparators(_inputs(_contract(kind="MILESTONE"), _schedule()))
    assert assessment.findings == []
    assert [o.reason for o in assessment.not_assessed] == ["DATE_KIND_NOT_COMPARABLE"]


# ── the golden-corpus path keeps its semantics ────────────────────────────────


@pytest.mark.unit
def test_bare_calibration_dates_still_compare_without_identity() -> None:
    inputs = ProjectCrossDocInputs(contract_deadline="2026-06-01", schedule_end="2026-09-01")
    assert isinstance(schedule_overruns_deadline(inputs), CrossDocFinding)


# ── assembly ─────────────────────────────────────────────────────────────────


def _contract_clause(clause_id: str, deadline: str, *, revision: str | None = REV_C) -> Clause:
    data: dict[str, object] = {
        "document_id": DOC_C,
        "completion_deadline": {"date": deadline, "kind": DATE_KIND_CONTRACT_COMPLETION},
    }
    if revision:
        data["evidence_location"] = {"revision_id": revision}
    return Clause(id=clause_id, text="Contract clause", data=data)


SCHEDULE_FINISH = {
    "document_id": DOC_S,
    "revision_id": REV_S,
    "date": "2027-09-30",
    "source_locator": "Plan!42",
}


@pytest.mark.unit
def test_assembly_builds_both_sources_with_identity_and_flags_the_overrun() -> None:
    clauses = [_contract_clause("clause-17", "2027-06-30")]

    inputs = assemble_cross_doc_inputs(clauses, schedule_planned_finish=SCHEDULE_FINISH)
    assert inputs.contract_completion == _contract()
    assert inputs.schedule_finish == _schedule()

    [signal] = cross_document_signals(clauses, schedule_planned_finish=SCHEDULE_FINISH)
    assert (signal.rule_id, signal.category) == ("DET-CRS-SCHDEAD", "TIME")
    assert signal.clause_id == "clause-17"  # the alert points at the contract clause
    assert signal.raw_data["evidence"]["observed"]["source_locator"] == "Plan!42"


@pytest.mark.unit
def test_two_contract_clauses_with_different_completion_dates_are_not_assessed() -> None:
    clauses = [
        _contract_clause("clause-17", "2027-06-30"),
        _contract_clause("clause-31", "2027-12-31"),
    ]
    inputs = assemble_cross_doc_inputs(clauses, schedule_planned_finish=SCHEDULE_FINISH)
    outcome = schedule_overruns_deadline(inputs)
    assert isinstance(outcome, CrossDocNotAssessed)
    assert "conflicting_contract_completion_dates" in outcome.detail
    assert cross_document_signals(clauses, schedule_planned_finish=SCHEDULE_FINISH) == []


@pytest.mark.unit
def test_the_same_date_stated_twice_is_one_completion_deadline() -> None:
    clauses = [
        _contract_clause("clause-17", "2027-06-30"),
        _contract_clause("clause-31", "2027-06-30"),
    ]
    inputs = assemble_cross_doc_inputs(clauses, schedule_planned_finish=SCHEDULE_FINISH)
    assert inputs.contract_completion is not None
    assert inputs.contract_completion.value == "2027-06-30"


@pytest.mark.unit
def test_a_contract_clause_not_bound_to_a_revision_is_not_assessed() -> None:
    clauses = [_contract_clause("clause-17", "2027-06-30", revision=None)]
    outcome = schedule_overruns_deadline(
        assemble_cross_doc_inputs(clauses, schedule_planned_finish=SCHEDULE_FINISH)
    )
    assert isinstance(outcome, CrossDocNotAssessed)
    assert outcome.reason == "UNSOURCED_DATE"


@pytest.mark.unit
def test_a_schedule_that_could_not_be_observed_is_not_assessed_with_its_reason() -> None:
    clauses = [_contract_clause("clause-17", "2027-06-30")]
    declared = {"document_id": DOC_S, "revision_id": REV_S, "reason": "evidence_parse_unavailable"}
    outcome = schedule_overruns_deadline(
        assemble_cross_doc_inputs(clauses, schedule_planned_finish=declared)
    )
    assert isinstance(outcome, CrossDocNotAssessed)
    assert outcome.reason == "DATE_NOT_ASSESSED"
    assert "evidence_parse_unavailable" in outcome.detail


@pytest.mark.unit
def test_other_clause_dates_are_never_read_as_the_completion_deadline() -> None:
    clauses = [
        Clause(id="m-1", text="Milestone", data={"deadline": "2027-01-31", "document_id": DOC_C}),
        Clause(id="t-1", text="Task", data={"end_date": "2027-02-28", "document_id": DOC_C}),
    ]
    assert assemble_cross_doc_inputs(clauses).contract_completion is None


# ── contract-side extraction ─────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("La fecha de finalización de las obras será el 30 de junio de 2027.", "2027-06-30"),
        ("La fecha de terminación contractual es 2027-06-30.", "2027-06-30"),
        ("The practical completion date shall be 30 June 2027.", "2027-06-30"),
        ("Completion date: June 30, 2027.", "2027-06-30"),
        ("Plazo general. La fecha de terminación de las obras es el 1 de febrero de 2028; "
         "las penalizaciones se aplican por día.", "2028-02-01"),
    ],
)
def test_a_clause_stating_the_completion_date_yields_a_completion_deadline(
    text: str, expected: str
) -> None:
    assert _extract_contract_completion_deadline(text) == {
        "date": expected,
        "kind": DATE_KIND_CONTRACT_COMPLETION,
        "basis": "stated_in_clause_text",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "El plazo de ejecución será de 18 meses desde la firma.",  # a duration, not a date
        "La fecha de finalización será el 30/06/2027.",  # DD/MM is ambiguous
        "Hito 2: la fecha de finalización de la cimentación es el 2027-01-31.",  # milestone
        "Partial completion date: 2027-01-31.",  # partial
        "El inicio de los trabajos es el 2027-01-31 y la fecha de finalización el 2027-12-31.",
        "La fecha de finalización será el 2027-06-30 o el 2027-07-15.",  # two dates, one sentence
        "La reunión será el 2027-06-30.",  # a date, but not a completion
        "La fecha de finalización se fijará de común acuerdo.",  # no date
    ],
)
def test_text_that_does_not_state_one_completion_date_yields_none(text: str) -> None:
    assert _extract_contract_completion_deadline(text) is None


# ── schedule-side summary ────────────────────────────────────────────────────


def _row(locator: str, start: object, end: object, task: str = "Task") -> dict[str, object]:
    return {"source_locator": locator, "start_date": start, "end_date": end, "task": task}


@pytest.mark.unit
def test_planned_finish_is_the_latest_observed_end_with_its_row_identity() -> None:
    doc, rev = uuid4(), uuid4()
    rows = [
        _row("Plan!2", datetime(2027, 1, 1), datetime(2027, 3, 1), "Foundations"),
        _row("Plan!3", datetime(2027, 3, 2), datetime(2027, 9, 30), "Handover"),
        _row("Plan!4", "05/06/2027", "07/06/2027", "Ambiguous locale"),
    ]
    summary = summarize_schedule_planned_finish(rows, document_id=doc, revision_id=rev)

    assert summary["date"] == "2027-09-30"
    assert summary["source_locator"] == "Plan!3"
    assert summary["activity"] == "Handover"
    assert (summary["document_id"], summary["revision_id"]) == (str(doc), str(rev))
    assert (summary["observed_rows"], summary["unassessed_rows"]) == (2, 1)
    assert summary["basis"] == "SOURCE_OBSERVED_NOT_APPROVED_BASELINE"


@pytest.mark.unit
def test_no_observable_row_records_a_reason_and_no_date() -> None:
    summary = summarize_schedule_planned_finish(
        [_row("Plan!2", "05/06/2027", "07/06/2027"), _row("Plan!3", None, None)],
        document_id=uuid4(),
        revision_id=uuid4(),
    )
    assert "date" not in summary
    assert summary["reason"] == "no_row_with_unambiguous_start_and_end"
    empty = summarize_schedule_planned_finish([], document_id=uuid4(), revision_id=uuid4())
    assert empty["reason"] == "no_schedule_rows"
