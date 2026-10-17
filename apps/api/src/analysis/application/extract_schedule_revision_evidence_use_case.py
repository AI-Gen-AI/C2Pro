"""PC-4: bind parsed schedule activities to a hash-verified document revision.

Read-only: this use case NEVER writes WBS, schedule tables or coherence scores.
A printed WBS code in the XLSX is a non-authoritative source label. Only a
separate explicit WBS node UUID may be checked against the current approved
baseline by the shared transactional WBS authority gate.
"""

from __future__ import annotations

import asyncio

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.schedule_activity_evidence import (
    InvalidScheduleEvidenceError,
    ScheduleActivityEvidence,
    observed_date_status,
)
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.application.document_source import verify_revision_file_hash
from src.documents.domain.models import Document, DocumentType
from src.temporal.domain.document_revision import DocumentRevision
from src.wbs.adapters.persistence.link_authority import require_linkable_wbs_nodes


class ScheduleApprovedScopeService(Protocol):
    async def require(
        self, *, tenant_id: UUID, project_id: UUID, node_ids: set[UUID]
    ) -> UUID: ...


@dataclass(frozen=True)
class AuthoritativeScheduleScopeService:
    """Use the existing WBS current-approved-baseline gate, not source WBS codes."""

    session: AsyncSession

    async def require(
        self, *, tenant_id: UUID, project_id: UUID, node_ids: set[UUID]
    ) -> UUID:
        authority = await require_linkable_wbs_nodes(
            self.session, tenant_id=tenant_id, project_id=project_id, node_ids=node_ids
        )
        if authority.baseline_id is None:
            raise InvalidScheduleEvidenceError("approved WBS baseline is missing")
        return authority.baseline_id


@dataclass(frozen=True)
class ScheduleRevisionEvidenceResult:
    rows: tuple[ScheduleActivityEvidence, ...]

    @property
    def time_assessment(self) -> str:
        # Even when dates are observed, no canonical TIME comparison is justified.
        return "NOT_ASSESSED"


@dataclass(frozen=True)
class ExtractScheduleRevisionEvidenceUseCase:
    parser: ExcelFileParser
    approved_scope_service: ScheduleApprovedScopeService

    async def execute(
        self,
        *,
        document: Document,
        revision: DocumentRevision,
        source_path: Path,
        existing_row_identities: Collection[tuple[UUID, str]] = (),
    ) -> ScheduleRevisionEvidenceResult:
        if document.document_type is not DocumentType.SCHEDULE:
            raise InvalidScheduleEvidenceError("source document is not a schedule")
        # Format is a property of the IMMUTABLE selected source revision.
        # The document's current filename/format may have changed on reupload.
        # A revision with no provable XLSX extension is NOT silently accepted.
        if Path(revision.blob_key).suffix.lower() != ".xlsx":
            raise InvalidScheduleEvidenceError(
                "selected source revision is not a supported XLSX schedule"
            )
        if (
            document.id != revision.document_id
            or document.tenant_id != revision.tenant_id
            or document.project_id != revision.project_id
        ):
            raise InvalidScheduleEvidenceError("document does not match immutable revision")

        # Hash BEFORE parsing; no fallback to mutable current document bytes.
        await asyncio.to_thread(verify_revision_file_hash, source_path, revision.blob_hash)
        parsed = await self.parser.parse_schedule(source_path, include_evidence=True)

        # Duplicated source IDs must not silently become two authoritative
        # activities; blank activity IDs are allowed and still have row identities.
        source_ids: set[str] = set()
        for row in parsed:
            activity_id = _optional_text(row.get("source_activity_id"))
            if activity_id is not None:
                if activity_id in source_ids:
                    raise InvalidScheduleEvidenceError("duplicate source activity id")
                source_ids.add(activity_id)

        known = set(existing_row_identities)
        new_rows = [
            row for row in parsed
            if (revision.revision_id, str(row["source_locator"])) not in known
        ]

        # No code-as-identity: only a source column explicitly named WBS Node ID
        # can supply a node UUID, and it MUST pass the approved baseline gate.
        node_by_locator: dict[str, UUID] = {}
        for row in new_rows:
            value = row.get("wbs_node_id")
            if value in (None, ""):
                continue
            try:
                node_by_locator[str(row["source_locator"])] = UUID(str(value))
            except (ValueError, AttributeError) as exc:
                raise InvalidScheduleEvidenceError("WBS Node ID is not a valid UUID") from exc

        approved_baseline_id: UUID | None = None
        if node_by_locator:
            approved_baseline_id = await self.approved_scope_service.require(
                tenant_id=revision.tenant_id,
                project_id=revision.project_id,
                node_ids=set(node_by_locator.values()),
            )

        result: list[ScheduleActivityEvidence] = []
        for row in new_rows:
            locator = str(row["source_locator"])
            name = _optional_text(row.get("task"))
            if not name:
                raise InvalidScheduleEvidenceError("schedule activity lacks source task")
            start, end, state, reason = observed_date_status(
                row.get("start_date"), row.get("end_date")
            )
            result.append(
                ScheduleActivityEvidence(
                    tenant_id=revision.tenant_id,
                    project_id=revision.project_id,
                    document_id=revision.document_id,
                    revision_id=revision.revision_id,
                    source_locator=locator,
                    activity_name=name,
                    source_activity_id=_optional_text(row.get("source_activity_id")),
                    source_milestone_id=_optional_text(row.get("source_milestone_id")),
                    source_wbs_code=_optional_text(row.get("wbs")),
                    wbs_node_id=node_by_locator.get(locator),
                    approved_wbs_baseline_id=(
                        approved_baseline_id if locator in node_by_locator else None
                    ),
                    start_date=start,
                    end_date=end,
                    duration_source=_optional_text(row.get("duration")),
                    predecessors_source=_optional_text(row.get("predecessors")),
                    date_state=state,
                    date_reason=reason,
                )
            )

        return ScheduleRevisionEvidenceResult(rows=tuple(result))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


__all__ = [
    "AuthoritativeScheduleScopeService",
    "ExtractScheduleRevisionEvidenceUseCase",
    "ScheduleApprovedScopeService",
    "ScheduleRevisionEvidenceResult",
]
