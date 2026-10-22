"""PC-4: immutable source observations of schedule activities, never canonical WBS.

A source activity, a milestone, and a WBS node are different entities.
A verified XLSX row can prove what its dates say, not an approved schedule
baseline, calendar, critical path, contractual compliance or TIME score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID


class InvalidScheduleEvidenceError(ValueError):
    """An observation claims an unverified source, duplicate ID or foreign scope."""


class ScheduleDateState(StrEnum):
    SOURCE_DATES_OBSERVED = "SOURCE_DATES_OBSERVED"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class ScheduleActivityEvidence:
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    source_locator: str
    activity_name: str
    source_activity_id: str | None
    source_milestone_id: str | None
    source_wbs_code: str | None
    wbs_node_id: UUID | None
    approved_wbs_baseline_id: UUID | None
    start_date: date | None
    end_date: date | None
    duration_source: str | None
    predecessors_source: str | None
    date_state: ScheduleDateState
    date_reason: str

    @property
    def identity(self) -> tuple[UUID, str]:
        return (self.revision_id, self.source_locator)


def observed_date(value: object) -> date | None:
    """Accept only unambiguous calendar dates; do not guess locale or timezone."""
    if isinstance(value, datetime):
        if value.tzinfo is not None or value.time() != time.min:
            return None
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    # ISO date only. DD/MM, numeric Excel serials and timestamps are ambiguous
    # without a declared locale/calendar/timezone and remain NOT_ASSESSED.
    if len(stripped) != 10 or stripped[4:5] != "-" or stripped[7:8] != "-":
        return None
    try:
        return date.fromisoformat(stripped)
    except ValueError:
        return None


def observed_date_status(
    start_source: object, end_source: object
) -> tuple[date | None, date | None, ScheduleDateState, str]:
    start = observed_date(start_source)
    end = observed_date(end_source)
    if start is None or end is None:
        return (start, end, ScheduleDateState.NOT_ASSESSED, "missing_or_ambiguous_source_date")
    if end < start:
        return (start, end, ScheduleDateState.NOT_ASSESSED, "source_end_before_start")
    # Source dates are verified observations ONLY; not approved time baselines.
    return (
        start,
        end,
        ScheduleDateState.SOURCE_DATES_OBSERVED,
        "contract_calendar_and_approved_schedule_comparison_missing",
    )


__all__ = [
    "InvalidScheduleEvidenceError",
    "ScheduleActivityEvidence",
    "ScheduleDateState",
    "observed_date",
    "observed_date_status",
]
