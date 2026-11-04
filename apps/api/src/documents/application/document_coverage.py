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
        "revision_id": str(revision_id) if revision_id is not None else None,
        "blob_hash": blob_hash,
        **coverage,
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
