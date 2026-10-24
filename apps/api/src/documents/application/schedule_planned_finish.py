"""Planned finish of a schedule revision, as a sourced observation (never a baseline).

PC-4 rule: a verified XLSX row proves what its dates say -- not an approved baseline, a
calendar or contractual compliance. This module therefore records only the latest end date
among the rows whose start AND end dates are unambiguous calendar dates, together with the
document, the hash-verified revision and the source row that carries it. When no row can be
observed it records WHY (``reason``) instead of a date, so the contract-vs-schedule
comparison is reported NOT_ASSESSED rather than guessed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from src.analysis.domain.schedule_activity_evidence import (
    ScheduleDateState,
    observed_date_status,
)
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError
from src.documents.application.document_source import (
    RevisionSourceError,
    read_verified_revision_file,
)

SCHEDULE_FINISH_BASIS = "SOURCE_OBSERVED_NOT_APPROVED_BASELINE"
METADATA_KEY = "schedule_planned_finish"


def summarize_schedule_planned_finish(
    rows: Iterable[Mapping[str, Any]],
    *,
    document_id: UUID,
    revision_id: UUID,
) -> dict[str, Any]:
    """The latest observed end date of a schedule revision, or the reason there is none."""
    identity = {"document_id": str(document_id), "revision_id": str(revision_id)}
    latest: tuple[Any, str, str] | None = None
    observed = 0
    unassessed = 0
    for row in rows:
        _, end, state, _ = observed_date_status(row.get("start_date"), row.get("end_date"))
        if state is not ScheduleDateState.SOURCE_DATES_OBSERVED or end is None:
            unassessed += 1
            continue
        observed += 1
        locator = str(row.get("source_locator") or "")
        if latest is None or end > latest[0]:
            latest = (end, locator, str(row.get("task") or ""))
    if latest is None:
        return {
            **identity,
            "reason": (
                "no_schedule_rows" if unassessed == 0 else "no_row_with_unambiguous_start_and_end"
            ),
            "unassessed_rows": unassessed,
            "basis": SCHEDULE_FINISH_BASIS,
        }
    end, locator, activity = latest
    if not locator:
        return {
            **identity,
            "reason": "source_row_locator_missing",
            "unassessed_rows": unassessed,
            "basis": SCHEDULE_FINISH_BASIS,
        }
    return {
        **identity,
        "date": end.isoformat(),
        "source_locator": locator,
        "activity": activity,
        "observed_rows": observed,
        "unassessed_rows": unassessed,
        "basis": SCHEDULE_FINISH_BASIS,
    }


async def extract_schedule_planned_finish(
    parser: ExcelFileParser,
    *,
    file_path: Path,
    file_format: str,
    document_id: UUID,
    revision_id: UUID | None,
    blob_hash: str | None,
) -> dict[str, Any]:
    """Re-read the pinned revision's bytes in evidence mode and summarise the planned finish.

    Never raises: any reason the finish cannot be observed becomes a recorded reason, because
    the ordinary ingestion of the schedule must not depend on this derived observation.
    """
    if revision_id is None or not blob_hash:
        return {
            "document_id": str(document_id),
            "reason": "no_pinned_revision",
            "basis": SCHEDULE_FINISH_BASIS,
        }
    identity = {"document_id": str(document_id), "revision_id": str(revision_id)}
    if file_format.lower() != ".xlsx":
        return {**identity, "reason": "unsupported_schedule_format", "basis": SCHEDULE_FINISH_BASIS}
    try:
        source_bytes = await asyncio.to_thread(read_verified_revision_file, file_path, blob_hash)
        rows = await parser.parse_schedule(
            file_path, include_evidence=True, source_bytes=source_bytes
        )
    except (ExcelParsingError, RevisionSourceError, OSError):
        return {**identity, "reason": "evidence_parse_unavailable", "basis": SCHEDULE_FINISH_BASIS}
    return summarize_schedule_planned_finish(rows, document_id=document_id, revision_id=revision_id)


__all__ = [
    "METADATA_KEY",
    "SCHEDULE_FINISH_BASIS",
    "extract_schedule_planned_finish",
    "summarize_schedule_planned_finish",
]
