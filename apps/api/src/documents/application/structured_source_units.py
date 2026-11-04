"""Persist source XLSX budget lines and schedule activities by immutable revision.

No WBS/BOM promotion, no generated embedding, no LLM. Source rows are evidence
observations only; neither a verified baseline nor an approved budget.
All SQL is staged inside the caller's processing-authority fenced transaction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError
from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral


_DELETE = text("""
    DELETE FROM public.document_source_units
    WHERE tenant_id = CAST(:tenant_id AS uuid)
      AND document_id = CAST(:document_id AS uuid)
      AND revision_id = CAST(:revision_id AS uuid)
      AND family = :family
""")

_INSERT = text("""
    INSERT INTO public.document_source_units
      (tenant_id, project_id, document_id, revision_id, blob_hash,
       family, source_locator, payload, unit_sha256)
    VALUES
      (CAST(:tenant_id AS uuid), CAST(:project_id AS uuid),
       CAST(:document_id AS uuid), CAST(:revision_id AS uuid), :blob_hash,
       :family, :source_locator, CAST(:payload AS jsonb), :unit_sha256)
""")


def _canonical_payload(row: dict[str, Any], *, kind: str) -> tuple[str, str]:
    """Preserve Decimal/date as strings without float conversions or lost precision."""
    raw = json.dumps(
        {"kind": kind, **row},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prepare_units(
    rows: list[dict[str, Any]],
    *,
    family: str,
    extra_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Validate unique row locators before any INSERT; fail on ambiguous origin."""
    prepared: list[dict[str, str]] = []
    seen: set[str] = set()
    for row, kind in (
        [(row, "activity" if family == "schedule" else "line_item") for row in rows]
        + [(row, "declared_total") for row in (extra_rows or [])]
    ):
        if not isinstance(row, dict):
            raise ValueError("SOURCE_UNIT_NOT_OBJECT")
        locator = row.get("source_locator")
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError("SOURCE_UNIT_LOCATOR_MISSING")
        if locator in seen:
            raise ValueError("SOURCE_UNIT_LOCATOR_DUPLICATED")
        seen.add(locator)
        payload, digest = _canonical_payload(row, kind=kind)
        prepared.append({
            "source_locator": locator,
            "payload": payload,
            "unit_sha256": digest,
        })
    return prepared


async def stage_structured_source_units(
    *,
    session: AsyncSession,
    parser: ExcelFileParser,
    file_path: Path,
    family: str,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    revision_id: UUID | None,
    blob_hash: str | None,
    source_format: str | None = None,
    parser_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reparse in strict evidence mode, then stage original source rows atomically.

    An Excel formula in a consumed field makes the source UNASSESSED; never use
    cached values as proof. An XLSX with other unprocessed worksheets is PARTIAL
    even though its active-sheet source rows remain useful observations.
    """
    if family not in {"budget", "schedule"}:
        raise ValueError("SOURCE_UNIT_FAMILY_INVALID")
    if revision_id is None or not blob_hash:
        return {"state": "UNASSESSED", "reason": "immutable_source_revision_missing", "units": 0}
    # R2 returns a temporary path; its suffix is usually preserved, but the
    # original verified document format remains the authoritative type.
    if (source_format or file_path.suffix).lower().lstrip(".") != "xlsx":
        return {"state": "UNASSESSED", "reason": "verified_source_format_unsupported", "units": 0}

    scope = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "document_id": str(document_id),
        "revision_id": str(revision_id),
        "blob_hash": blob_hash,
        "family": family,
    }

    # Replaying identical immutable bytes must never create duplicate source
    # observations or leave a previous extraction visible after a failed reparse.
    await session.execute(_DELETE, scope)
    try:
        if family == "budget":
            verified_rows = await parser.parse_budget(file_path, include_evidence=True)
            supplementary = getattr(verified_rows, "declared_total_rows", [])
        else:
            verified_rows = await parser.parse_schedule(file_path, include_evidence=True)
            supplementary = []
    except ExcelParsingError as exc:
        reason = (
            "unverified_formula_or_source_cell"
            if "formula" in str(exc).lower()
            else "verified_evidence_parser_rejected_source"
        )
        return {"state": "UNASSESSED", "reason": reason, "units": 0}

    prepared = _prepare_units(
        verified_rows, family=family, extra_rows=supplementary
    )
    if prepared:
        for start in range(0, len(prepared), 250):
            await session.execute(
                _INSERT,
                [{**scope, **row} for row in prepared[start : start + 250]],
            )

    parser_status = (
        str(parser_coverage.get("status", "UNVERIFIED"))
        if isinstance(parser_coverage, dict)
        else "UNVERIFIED"
    )
    return {
        "state": "SOURCE_OBSERVED" if prepared else "UNASSESSED",
        "reason": "rows_observed_not_approved_baseline" if prepared else "no_verified_source_rows",
        "units": len(prepared),
        "parser_coverage": parser_status,
        "source_scope": "active_worksheet_only",
    }




_READ_TRUSTED_SOURCE_UNITS = text(f"""
    SELECT u.document_id, u.revision_id, u.source_locator, u.family,
           u.blob_hash, u.unit_sha256, u.payload
    FROM public.document_source_units AS u
    JOIN public.documents AS d
      ON d.id = u.document_id
     AND d.project_id = u.project_id
     AND d.tenant_id = u.tenant_id
    CROSS JOIN LATERAL {current_revision_lateral("u.document_id", "u.tenant_id")} AS cur
    WHERE u.tenant_id = CAST(:tenant_id AS uuid)
      AND u.project_id = CAST(:project_id AS uuid)
      AND u.family = :family
      AND cur.canonical
      AND cur.revision_id = u.revision_id
    ORDER BY u.document_id, u.source_locator
""")


async def load_canonical_source_units(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    family: str,
) -> list[dict[str, Any]]:
    """Read only original rows of canonical document revisions, never pending ones.

    This is a source-evidence reader; it does NOT approve an EPC baseline, prove
    entire workbook coverage or create N8 risk/coherence signals.
    """
    if family not in {"budget", "schedule"}:
        raise ValueError("SOURCE_UNIT_FAMILY_INVALID")

    result = await session.execute(
        _READ_TRUSTED_SOURCE_UNITS,
        {
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "family": family,
        },
    )
    return [
        dict(row)
        for row in result.mappings().all()
    ]


__all__ = ["stage_structured_source_units", "load_canonical_source_units"]
