"""A11: honest physical-page ↔ text-offset provenance pinned to a PDF revision.

Only source labels and offsets cross the metadata boundary; the original text
remains in revision-scoped parsed_text and is never duplicated into page maps.
DOCX page=1 placeholders are NOT physical PDF pages.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import UUID

PAGE_SPANS_KEY = "parsed_text_page_spans_by_revision"
_PAGE_STATUSES = frozenset({
    "NATIVE_TEXT", "OCR_ONLY", "OCR_AUGMENTED", "OCR_REPLACED_SUSPECT",
    "OCR_UNAVAILABLE", "OCR_FAILED", "OCR_EMPTY_RESULT", "OCR_UNCLASSIFIED",
    "SPARSE_TEXT_UNVERIFIED", "SPARSE_OCR_FAILED", "SPARSE_OCR_EMPTY",
    "NO_TEXT_UNASSESSED", "SUSPECT_NATIVE_TEXT_UNVERIFIED",
    "OCR_DUPLICATE_IGNORED",
})
_PAGE_REASONS = frozenset({
    "none", "no_native_text", "sparse_native_text", "suspect_native_text",
})


def record_revision_page_spans(
    metadata: dict[str, Any], *, parsed_payload: dict[str, Any],
    parsed_text: str, revision_id: UUID | None, blob_hash: str | None,
) -> None:
    """Record source-observed PDF page mapping, never synthesize printed pages.

    The block layout is exactly the same join/strip as both ingestion paths.
    If it differs from actual text, offsets must NOT be published as valid.
    """
    if revision_id is None or not isinstance(blob_hash, str):
        return
    if parsed_payload.get("file_format") != ".pdf":
        return
    coverage = parsed_payload.get("document_coverage")
    if not isinstance(coverage, dict) or coverage.get("origin") != "pdf_file_parser":
        return
    inventory = coverage.get("source_inventory")
    if not isinstance(inventory, dict) or inventory.get("inspection_available") is not True:
        return
    count = inventory.get("source_pages")
    if type(count) is not int or count < 1:
        return

    block_rows = parsed_payload.get("text_blocks")
    if not isinstance(block_rows, list):
        return
    blocks = [
        b for b in block_rows if isinstance(b, dict) and isinstance(b.get("text"), str)
    ]
    joined = "\n\n".join(b["text"] for b in blocks)
    alignment_valid = joined.strip() == parsed_text
    leading_trim = len(joined) - len(joined.lstrip())
    spans: list[dict[str, Any]] = []
    position = 0
    for index, block in enumerate(blocks):
        source_text = block["text"]
        start = position - leading_trim
        end = start + len(source_text)
        position += len(source_text) + (2 if index < len(blocks) - 1 else 0)
        if not source_text.strip():
            continue
        if start < 0 or end > len(parsed_text) or parsed_text[start:end] != source_text:
            alignment_valid = False
            continue
        label = block.get("page")
        physical_page = label if type(label) is int and 1 <= label <= count else None
        spans.append({
            "block_index": index,
            "page": physical_page,
            "start_offset": start,
            "end_offset": end,
            "method": "OCR" if block.get("ocr") is True else "NATIVE",
            "page_verified": physical_page is not None,
        })

    # A parser diagnostic is an observed status, not a completeness claim.
    page_analysis = coverage.get("page_analysis")
    pages: list[dict[str, Any]] = []
    seen: set[int] = set()
    if isinstance(page_analysis, list):
        for item in page_analysis:
            if not isinstance(item, dict):
                continue
            page = item.get("page")
            status = item.get("status")
            if (type(page) is not int or not 1 <= page <= count or
                    page in seen or status not in _PAGE_STATUSES):
                continue
            reason = item.get("reason")
            pages.append({
                "page": page,
                "status": status,
                "reason": reason if reason in _PAGE_REASONS else "none",
            })
            seen.add(page)
    observed_pages = {s["page"] for s in spans if s["page"] is not None}
    for page in range(1, count + 1):
        if page not in seen:
            pages.append({
                "page": page,
                "status": "TEXT_OBSERVED_UNASSESSED" if page in observed_pages
                          else "NO_DIAGNOSTIC",
                "reason": "diagnostic_unavailable",
            })
    pages.sort(key=lambda item: item["page"])

    entry = {
        "revision_id": str(revision_id),
        "blob_hash": blob_hash,
        "parsed_text_sha256": sha256(parsed_text.encode("utf-8")).hexdigest(),
        "status": "OBSERVED_ONLY" if alignment_valid else "TEXT_ALIGNMENT_UNVERIFIED",
        "origin": "pdf_file_parser",
        "source_pages": count,
        "spans": spans if alignment_valid else [],
        "pages": pages,
    }
    mapped = dict(metadata.get(PAGE_SPANS_KEY) or {})
    mapped[str(revision_id)] = entry
    metadata[PAGE_SPANS_KEY] = mapped


def read_revision_page_spans(
    metadata: dict[str, Any] | None, *, parsed_text: str, revision: Any,
) -> dict[str, Any] | None:
    """Fail closed for stale, foreign, incomplete or unpinned page maps."""
    if not isinstance(metadata, dict) or revision is None:
        return None
    rid = str(getattr(revision, "revision_id", ""))
    items = metadata.get(PAGE_SPANS_KEY)
    entry = items.get(rid) if isinstance(items, dict) else None
    if not isinstance(entry, dict):
        return None
    if (entry.get("revision_id") != rid
            or entry.get("blob_hash") != getattr(revision, "blob_hash", None)
            or entry.get("origin") != "pdf_file_parser"
            or entry.get("status") != "OBSERVED_ONLY"
            or entry.get("parsed_text_sha256") != sha256(parsed_text.encode("utf-8")).hexdigest()
            or metadata.get("parsed_text_revision_id") != rid
            or metadata.get("parsed_text") != parsed_text):
        return None
    return entry



# A9 takes exactly one PageSpan per page, in strictly increasing physical
# ordinal order. A11's canonical spans are per block, never change them:
# they preserve source offsets, including native text on OCR-failed pages.
_A9_LOCATABLE_PAGE_STATES = frozenset({
    "NATIVE_TEXT", "OCR_ONLY", "OCR_AUGMENTED",
    "OCR_REPLACED_SUSPECT", "OCR_DUPLICATE_IGNORED",
})


def read_a9_physical_page_map(
    metadata: dict[str, Any] | None,
    *,
    parsed_text: str,
    revision: Any,
) -> dict[str, Any] | None:
    """Return A9-compatible page rows, only from an authenticated A11 PDF map.

    Page observations remain UNVERIFIED against full PDF contents. This
    projection never certifies legal evidence or an OCR word bounding box.
    A9 locates observed parser text, not the underlying document image.

    None = invalid/stale map (fail closed); a non-None map with an empty
    spans list = valid lineage but no safely locatable page.
    """
    raw = read_revision_page_spans(
        metadata, parsed_text=parsed_text, revision=revision,
    )
    if raw is None:
        return None

    count = raw.get("source_pages")
    pages = raw.get("pages")
    blocks = raw.get("spans")
    if (
        type(count) is not int or count < 1 or count > 10_000
        or not isinstance(pages, list) or len(pages) != count
        or not isinstance(blocks, list)
    ):
        return None

    page_status: dict[int, str] = {}
    for item in pages:
        if not isinstance(item, dict):
            return None
        page = item.get("page")
        status = item.get("status")
        if (
            type(page) is not int or not 1 <= page <= count
            or page in page_status or not isinstance(status, str)
        ):
            return None
        page_status[page] = status

    # Audit the FULL block map before excluding unsafe pages. Any overlap,
    # misalignment, missing non-whitespace characters, unlocated page, or
    # out-of-order physical page invalidates the entire projection.
    cursor = 0
    previous_page = 0
    page_rows: list[dict[str, int]] = []
    for block in blocks:
        if not isinstance(block, dict):
            return None
        page = block.get("page")
        start = block.get("start_offset")
        end = block.get("end_offset")
        method = block.get("method")
        if (
            type(page) is not int or not 1 <= page <= count
            or block.get("page_verified") is not True
            or type(start) is not int or type(end) is not int
            or not 0 <= cursor <= start < end <= len(parsed_text)
            or page < previous_page
            or not isinstance(method, str)
            or method not in {"OCR", "NATIVE"}
            or parsed_text[cursor:start].strip()
            or not parsed_text[start:end].strip()
        ):
            return None
        status = page_status[page]
        if (
            (status in {"OCR_ONLY", "OCR_REPLACED_SUSPECT"} and method != "OCR")
            or (status in {"NATIVE_TEXT", "OCR_DUPLICATE_IGNORED"} and method != "NATIVE")
        ):
            return None

        if page_rows and page_rows[-1]["page"] == page:
            # The inter-block separator is already part of parsed_text,
            # so extending the span does not rewrite any original offsets.
            page_rows[-1]["end_offset"] = end
        else:
            page_rows.append({
                "page": page,
                "start_offset": start,
                "end_offset": end,
            })
        previous_page = page
        cursor = end
    if parsed_text[cursor:].strip():
        return None

    excluded = [
        {"page": page, "reason": page_status[page]}
        for page in range(1, count + 1)
        if page_status[page] not in _A9_LOCATABLE_PAGE_STATES
    ]
    safe_rows = [
        row for row in page_rows
        if page_status[row["page"]] in _A9_LOCATABLE_PAGE_STATES
    ]
    if not safe_rows:
        projection_status = "NO_LOCATABLE_PAGES"
    elif excluded:
        projection_status = "PARTIAL"
    else:
        projection_status = "OBSERVED_ONLY"

    return {
        "schema_version": "a11-a9-physical-page-map-v1",
        "revision_id": raw["revision_id"],
        "blob_hash": raw["blob_hash"],
        "parsed_text_sha256": raw["parsed_text_sha256"],
        "source_pages": count,
        "source_kind": "PDF_PHYSICAL_PAGE_OBSERVATION",
        "status": projection_status,
        "spans": safe_rows,
        "excluded_pages": excluded,
        "original_document_completeness_certified": False,
    }
