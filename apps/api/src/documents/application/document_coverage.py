"""Revision-scoped, honest document-coverage metadata."""

from __future__ import annotations

from typing import Any
from uuid import UUID

COVERAGE_METADATA_KEY = "document_coverage_by_revision"
_VALID_COVERAGE_STATES = frozenset({"COMPLETE", "PARTIAL", "UNSUPPORTED", "UNVERIFIED"})


def record_revision_document_coverage(
    metadata: dict[str, Any],
    *,
    parsed_payload: dict[str, Any],
    revision_id: UUID | None,
    blob_hash: str | None,
) -> None:
    """Store parser-reported coverage without conflating it with parse status."""
    coverage = parsed_payload.get("document_coverage")
    if not isinstance(coverage, dict):
        return
    status = coverage.get("status")
    origin = coverage.get("origin")
    if status not in _VALID_COVERAGE_STATES or not isinstance(origin, str):
        return

    stamped_coverage = {
        **coverage,
        # Server-derived identity wins even if the parser payload accidentally
        # supplies similarly named fields.
        "revision_id": str(revision_id) if revision_id is not None else None,
        "blob_hash": blob_hash,
        "parser_observations": summarize_parser_observations(parsed_payload),
    }
    if revision_id is None:
        # Legacy documents have no immutable revision identity. Preserve the
        # limitation, but never present it as revision-scoped evidence.
        metadata["document_coverage"] = stamped_coverage
        return

    coverage_by_revision = dict(metadata.get(COVERAGE_METADATA_KEY) or {})
    coverage_by_revision[str(revision_id)] = stamped_coverage
    metadata[COVERAGE_METADATA_KEY] = coverage_by_revision


def append_document_coverage_omissions(
    metadata: dict[str, Any], *, revision_id: UUID | None, omissions: list[dict[str, Any]]
) -> None:
    """Record identified omissions without adding source text to metadata."""
    if not omissions:
        return
    if revision_id is None:
        coverage = metadata.get("document_coverage")
    else:
        coverage = (metadata.get(COVERAGE_METADATA_KEY) or {}).get(str(revision_id))
    if not isinstance(coverage, dict):
        return
    existing = list(coverage.get("known_omissions") or [])
    coverage["known_omissions"] = [*existing, *omissions]



def summarize_parser_observations(parsed_payload: dict[str, Any]) -> dict[str, Any]:
    """Count *observed* parser units, never claim completeness against the source.

    This manifest contains aggregate counts only; no contract prose, cells,
    filenames or identifiers are copied into document metadata. Sheet/formula
    coverage and source caveats continue to come from each parser's own
    document_coverage payload. A zero count is meaningful, not a success flag.
    """
    observations: dict[str, Any] = {}

    if isinstance(parsed_payload.get("text_blocks"), list):
        blocks = [
            block for block in parsed_payload["text_blocks"]
            if isinstance(block, dict)
            and isinstance(block.get("text"), str)
            and block["text"].strip()
        ]
        observations["text_blocks"] = {
            "count": len(blocks),
            "characters": sum(len(block["text"]) for block in blocks),
            # DOCX parsers can emit a placeholder page=1; these are parser
            # labels, NOT proof of actual printed source-page coverage.
            "parser_page_labels": sorted({
                block["page"] for block in blocks
                if isinstance(block.get("page"), int) and block["page"] > 0
            }),
        }

    schedule = parsed_payload.get("schedule")
    if isinstance(schedule, list):
        rows = [row for row in schedule if isinstance(row, dict)]
        observations["schedule"] = {
            "parsed_rows": len(rows),
            "rows_with_source_locator": sum(
                bool(row.get("source_locator")) for row in rows
            ),
            "rows_with_task": sum(bool(row.get("task")) for row in rows),
            "rows_with_predecessors": sum(
                bool(row.get("predecessors")) for row in rows
            ),
        }

    budget = parsed_payload.get("budget")
    if isinstance(budget, list):
        rows = [row for row in budget if isinstance(row, dict)]
        declared = getattr(budget, "declared_total_rows", [])
        observations["budget"] = {
            "parsed_line_items": len(rows),
            "items_with_source_locator": sum(
                bool(row.get("source_locator")) for row in rows
            ),
            "declared_total_rows": (
                len(declared) if isinstance(declared, list) else 0
            ),
            "has_declared_total": getattr(budget, "stated_total", None) is not None,
        }
    elif isinstance(budget, dict):
        chapters = budget.get("chapters")
        observations["budget"] = {
            "parsed_chapters": len(chapters) if isinstance(chapters, list) else 0,
            "chapter_line_item_counts_known": False,
            "has_declared_total": budget.get("stated_total") is not None,
        }

    clauses = parsed_payload.get("clauses")
    if isinstance(clauses, list):
        observations["clauses"] = {
            "parsed_entries": sum(isinstance(item, dict) for item in clauses)
        }

    return observations


# N12 source attestation is a revision-anchored parser claim, not legal or
# semantic verification of extracted clauses. No currently deployed PDF/DOCX
# parser emits the required verified_full_source_text assurance.
N12_TEXT_DIGEST_KEY = "n12_parsed_text_sha256_by_revision"
_N12_TEXT_ORIGINS = frozenset({"pdf_file_parser", "docx_file_parser"})


def record_revision_parsed_text_digest(
    metadata: dict[str, Any], *, parsed_text: str, revision_id: UUID | None
) -> None:
    """Stamp the exact text stored by ingestion; no prose in the digest record."""
    from hashlib import sha256

    if revision_id is None or not parsed_text:
        return
    hashes = dict(metadata.get(N12_TEXT_DIGEST_KEY) or {})
    hashes[str(revision_id)] = sha256(parsed_text.encode("utf-8")).hexdigest()
    metadata[N12_TEXT_DIGEST_KEY] = hashes


def build_n12_source_attestation(
    *,
    metadata: dict[str, Any] | None,
    parsed_text: str,
    revision: Any,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
) -> dict[str, str] | None:
    """Accept only externally revision-pinned, explicitly assured parser text.

    The revision must come from a tenant-scoped revision repository, not from
    metadata. COMPLETE by itself and mere text length are never assurance.
    False or missing attestation means N12 stays UNASSESSED and routes to HITL.
    """
    from hashlib import sha256
    import re

    if not metadata or not parsed_text or revision is None:
        return None

    if (
        revision.tenant_id != tenant_id
        or revision.project_id != project_id
        or revision.document_id != document_id
        or not isinstance(revision.blob_hash, str)
        or re.fullmatch(r"[0-9a-fA-F]{64}", revision.blob_hash) is None
    ):
        return None

    revision_id = str(revision.revision_id)
    coverage_by_revision = metadata.get(COVERAGE_METADATA_KEY)
    if not isinstance(coverage_by_revision, dict):
        return None
    coverage = coverage_by_revision.get(revision_id)
    if not isinstance(coverage, dict):
        return None
    if (
        coverage.get("revision_id") != revision_id
        or coverage.get("blob_hash") != revision.blob_hash
        or coverage.get("status") != "COMPLETE"
        or coverage.get("origin") not in _N12_TEXT_ORIGINS
        or coverage.get("text_coverage_assurance") != "verified_full_source_text"
        or coverage.get("limitations")
        or coverage.get("known_omissions")
    ):
        return None

    observed = coverage.get("parser_observations")
    units = observed.get("text_blocks") if isinstance(observed, dict) else None
    if (
        not isinstance(units, dict)
        or type(units.get("count")) is not int
        or units["count"] <= 0
        or type(units.get("characters")) is not int
        or units["characters"] <= 0
    ):
        return None

    digests = metadata.get(N12_TEXT_DIGEST_KEY)
    digest = sha256(parsed_text.encode("utf-8")).hexdigest()
    if (
        not isinstance(digests, dict)
        or digests.get(revision_id) != digest
        or metadata.get("parsed_text_revision_id") != revision_id
        or metadata.get("parsed_text") != parsed_text
    ):
        return None

    return {
        "revision_id": revision_id,
        "document_id": str(document_id),
        "project_id": str(project_id),
        "tenant_id": str(tenant_id),
        "blob_hash": revision.blob_hash,
        "parsed_text_sha256": digest,
    }
