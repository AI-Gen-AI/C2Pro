"""Controlled re-extraction of the original XLSX source rows of ONE existing budget revision.

An already analysed budget revision keeps its document, revision, ``rev_no`` and ``blob_hash``.
Only the derived, deterministic evidence is recomputed from the verified original bytes:

* ``document_source_units`` of that revision (via ``stage_structured_source_units``), and
* the revision-keyed ``source_units_by_revision`` / ``stated_total_by_revision`` summaries.

It never touches processing authority, analysis, review items, HITL decisions, alerts or scores,
does not re-run any graph node, and makes no LLM call. Everything happens in one transaction
guarded by a document row lock and the revision-lineage advisory lock; any failed precondition
raises before a single derived row is written, and the savepoint around the restage is rolled back
if the result is not a verified observation. A second identical run changes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.application.budget_stated_total import record_revision_stated_total
from src.documents.application.document_source import RevisionSourceError, fetch_source_file
from src.documents.application.parse_document_use_case import (
    _extract_budget_currencies,
    _extract_budget_stated_total,
)
from src.documents.application.structured_source_units import stage_structured_source_units
from src.documents.domain.models import DocumentStatus, DocumentType

_REEXTRACTABLE_STATUSES = frozenset(
    {DocumentStatus.ANALYZED.value, DocumentStatus.PARSED_PENDING_ANALYSIS.value}
)

_LOCK_DOCUMENT = text("""
    SELECT upload_status FROM public.documents
    WHERE id = CAST(:document_id AS uuid)
      AND tenant_id = CAST(:tenant_id AS uuid)
      AND project_id = CAST(:project_id AS uuid)
    FOR UPDATE
""")

_READ_UNITS = text("""
    SELECT source_locator, unit_sha256
    FROM public.document_source_units
    WHERE tenant_id = CAST(:tenant_id AS uuid)
      AND document_id = CAST(:document_id AS uuid)
      AND revision_id = CAST(:revision_id AS uuid)
      AND family = 'budget'
""")


class BudgetReextractionError(Exception):
    """A precondition failed; nothing was written. ``code`` is stable, ``status_code`` is HTTP."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _normalize_hash(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    return cleaned.removeprefix("sha256:")


async def _unit_digests(session: AsyncSession, scope: dict[str, str]) -> dict[str, str]:
    rows = (await session.execute(_READ_UNITS, scope)).all()
    return {str(row[0]): str(row[1]) for row in rows}


async def reextract_budget_source_units(
    *,
    session: AsyncSession,
    document_repository: Any,
    revision_repository: Any,
    storage: Any,
    file_parser: Any,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    expected_revision_id: UUID,
    expected_blob_hash: str,
) -> dict[str, Any]:
    """Recompute the source rows of ``expected_revision_id``; commit once, or raise untouched."""
    document = await document_repository.get_by_id(tenant_id, document_id)
    if document is None or document.project_id != project_id:
        raise BudgetReextractionError("DOCUMENT_NOT_FOUND", 404)
    if document.document_type != DocumentType.BUDGET:
        raise BudgetReextractionError("DOCUMENT_NOT_BUDGET", 409)
    if (document.file_format or "").lower().lstrip(".") != "xlsx":
        raise BudgetReextractionError("SOURCE_FORMAT_NOT_XLSX", 409)

    try:
        # Serialise with re-uploads/approvals (lineage) and with any other writer of this row.
        await revision_repository.lock_lineage(document_id, tenant_id)
        locked = (
            await session.execute(
                _LOCK_DOCUMENT,
                {
                    "document_id": str(document_id),
                    "tenant_id": str(tenant_id),
                    "project_id": str(project_id),
                },
            )
        ).scalar_one_or_none()
        if locked is None:
            raise BudgetReextractionError("DOCUMENT_NOT_FOUND", 404)
        if str(getattr(locked, "value", locked)) not in _REEXTRACTABLE_STATUSES:
            # uploaded/queued/processing: a worker may own it; error: use the normal retry path.
            raise BudgetReextractionError("DOCUMENT_STATE_NOT_REEXTRACTABLE", 409)

        revision = await revision_repository.get_current(document_id, tenant_id)
        if revision is None or revision.revision_id != expected_revision_id:
            raise BudgetReextractionError("REVISION_NOT_CURRENT", 409)
        if (
            _normalize_hash(revision.blob_hash) != _normalize_hash(expected_blob_hash)
            or not _normalize_hash(revision.blob_hash)
        ):
            raise BudgetReextractionError("REVISION_HASH_PRECONDITION_FAILED", 409)

        file_path: Path | None = None
        try:
            # Downloads the immutable object and verifies its SHA-256 against the revision.
            file_path = await fetch_source_file(
                storage=storage, document=document, revision=revision
            )
            parsed_payload = await file_parser.parse_document_file(document, file_path)

            scope = {
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "revision_id": str(revision.revision_id),
            }
            before = await _unit_digests(session, scope)

            savepoint = await session.begin_nested()
            summary = await stage_structured_source_units(
                session=session,
                parser=file_parser.excel_parser,
                file_path=file_path,
                family="budget",
                tenant_id=tenant_id,
                project_id=project_id,
                document_id=document_id,
                revision_id=revision.revision_id,
                blob_hash=revision.blob_hash,
                source_format=document.file_format,
                parser_coverage=parsed_payload.get("document_coverage"),
            )
            if summary.get("state") != "SOURCE_OBSERVED":
                await savepoint.rollback()
                raise BudgetReextractionError(
                    f"REEXTRACTION_NOT_OBSERVED:{summary.get('reason', 'unknown')}", 422
                )
            after = await _unit_digests(session, scope)
            if after == before:
                # Idempotent replay: keep the original rows (ids, timestamps) untouched.
                await savepoint.rollback()
            else:
                await savepoint.commit()
        finally:
            if file_path is not None:
                file_path.unlink(missing_ok=True)

        metadata = dict(document.document_metadata or {})
        previous_metadata = dict(metadata)
        summaries = dict(metadata.get("source_units_by_revision") or {})
        summaries[str(revision.revision_id)] = summary
        metadata["source_units_by_revision"] = summaries
        record_revision_stated_total(
            metadata,
            revision_id=revision.revision_id,
            blob_hash=revision.blob_hash,
            total=_extract_budget_stated_total(parsed_payload),
            currencies=_extract_budget_currencies(parsed_payload)
            if _extract_budget_stated_total(parsed_payload) is not None
            else None,
            source_locator=getattr(
                parsed_payload.get("budget"), "stated_total_locator", None
            ),
        )
        metadata_changed = metadata != previous_metadata
        if metadata_changed:
            await document_repository.update_metadata(tenant_id, document_id, metadata)

        await session.commit()
    except BudgetReextractionError:
        await session.rollback()
        raise
    except RevisionSourceError as exc:
        await session.rollback()
        raise BudgetReextractionError(f"REVISION_SOURCE_INVALID:{exc}", 409) from exc
    except Exception:
        await session.rollback()
        raise

    return {
        "document_id": str(document_id),
        "revision_id": str(revision.revision_id),
        "blob_hash": revision.blob_hash,
        "units_before": len(before),
        "units_after": len(after),
        "changed": after != before or metadata_changed,
        "added_locators": sorted(set(after) - set(before)),
        "removed_locators": sorted(set(before) - set(after)),
        "summary": summary,
    }


__all__ = ["BudgetReextractionError", "reextract_budget_source_units"]
