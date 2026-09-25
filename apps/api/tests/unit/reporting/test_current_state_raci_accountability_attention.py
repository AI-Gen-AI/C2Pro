"""'What needs attention' names WBS tasks nobody is accountable for (P0d product value).

The RACI section already counts tasks without an Accountable party, but a Project or
Contract Manager reading the executive summary never saw it: an accountability gap on a
WBS task is a governance risk that should surface where attention is decided. When no
RACI assignment exists at all, the action is to start RACI, so the item says that.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.reporting.application.current_state_projection import assemble_current_state_report
from src.reporting.application.ports import (
    CurrentStateInputs,
    SourceFailed,
    SourceOk,
    SourceUnavailable,
)
from src.reporting.domain.current_state_report import ProjectIdentity, SectionStatus
from src.stakeholders.application.dtos import (
    RaciMatrixAssignment,
    RaciMatrixTaskRow,
    RaciMatrixViewResponse,
)

GENERATED_AT = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
PROJECT = ProjectIdentity(id=uuid4(), name="Harbour Extension", code="HX-01", status="active")


def _row(code: str, *roles: str) -> RaciMatrixTaskRow:
    return RaciMatrixTaskRow(
        task_id=uuid4(),
        task_code=code,
        task_name=f"Task {code}",
        sequence_index=0,
        assignments=[
            RaciMatrixAssignment(stakeholder_id=uuid4(), stakeholder_name=f"{role} person", role=role, is_verified=False)
            for role in roles
        ],
    )


def _report(raci: object):
    unavailable = SourceUnavailable("not part of this test")
    inputs = CurrentStateInputs(
        documents=unavailable,
        health=unavailable,
        coherence=unavailable,
        alerts=unavailable,
        hitl=unavailable,
        budget=unavailable,
        wbs=unavailable,
        stakeholders=unavailable,
        raci=raci,  # type: ignore[arg-type]
    )
    return assemble_current_state_report(PROJECT, inputs, generated_at=GENERATED_AT)


def _attention(raci: object) -> list[tuple[str, str, str]]:
    summary = _report(raci).sections.executive_summary
    assert summary.data is not None
    # Only accountability items: a failed RACI source is already reported as section_error.
    return [
        (item.kind, item.level, item.message)
        for item in summary.data.attention_items
        if item.kind.startswith("raci_")
    ]


def test_tasks_without_an_accountable_party_need_attention() -> None:
    matrix = RaciMatrixViewResponse(
        matrix=[
            _row("1.1", "ACCOUNTABLE", "RESPONSIBLE"),
            _row("1.2", "RESPONSIBLE"),
            _row("1.3"),
        ]
    )

    assert _attention(SourceOk(matrix)) == [
        (
            "raci_tasks_without_accountable",
            "warning",
            "2 WBS task(s) have no accountable party in the RACI matrix.",
        ),
    ]


def test_a_matrix_without_any_assignment_says_raci_has_not_started() -> None:
    matrix = RaciMatrixViewResponse(matrix=[_row("1.1"), _row("1.2")])

    assert _attention(SourceOk(matrix)) == [
        (
            "raci_not_started",
            "warning",
            "No RACI assignments exist yet; none of the 2 WBS task(s) has an accountable party.",
        ),
    ]


def test_no_accountability_attention_when_every_task_has_an_accountable_party() -> None:
    matrix = RaciMatrixViewResponse(matrix=[_row("1.1", "ACCOUNTABLE"), _row("1.2", "RESPONSIBLE", "ACCOUNTABLE")])

    assert _attention(SourceOk(matrix)) == []


def test_unknown_raci_is_not_reported_as_an_accountability_gap() -> None:
    assert _attention(SourceOk(RaciMatrixViewResponse(matrix=[]))) == []
    assert _attention(SourceUnavailable("RACI generation disabled")) == []
    assert _attention(SourceFailed("RACI source raised")) == []


def test_an_empty_matrix_means_there_are_no_wbs_tasks() -> None:
    raci = _report(SourceOk(RaciMatrixViewResponse(matrix=[]))).sections.raci

    assert raci.status is SectionStatus.EMPTY
    assert raci.status_reason == "No WBS tasks exist yet, so there is no RACI matrix."
