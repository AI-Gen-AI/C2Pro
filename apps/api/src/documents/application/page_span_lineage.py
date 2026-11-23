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
