"""I-C01: optional Docling contract/annex structural evidence adapter.

Research-only port: does not call N4/N12, mutate HITL, ProjectGraph or Scores,
nor alter C2Pro's current PDF parser or upload routing. Content is NEVER
marked trusted or legally interpreted by this adapter.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

MAX_PDF_BYTES = 24 * 1024 * 1024
MAX_PAGES = 300
MAX_TEXT_ITEMS = 100_000
MAX_TABLE_CELLS = 150_000
DOCUMENT_KINDS = frozenset({"contract", "annex", "specification", "other"})


class ContractEvidenceParseError(ValueError):
    """Fail-closed structural parsing; error messages must not expose source text."""


@dataclass(frozen=True)
class DocumentEvidenceScope:
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, key), UUID) for key in (
            "tenant_id", "project_id", "document_id", "revision_id"
        )):
            raise ContractEvidenceParseError("source scope requires UUID identifiers")


def _make_docling_converter(*, ocr_enabled: bool) -> Any:
    """Load optional heavy dependency only when this research adapter is used."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        options = PdfPipelineOptions()
        options.do_ocr = ocr_enabled
        options.do_table_structure = True
        return DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
    except Exception as exc:
        raise ContractEvidenceParseError(
            f"Docling converter unavailable ({type(exc).__name__})"
        ) from None


def _bbox(provenance: Any) -> list[float] | None:
    bbox = getattr(provenance, "bbox", None)
    if bbox is None:
        return None
    try:
        return [float(getattr(bbox, k)) for k in ("l", "t", "r", "b")]
    except (TypeError, ValueError, AttributeError):
        return None


def _locations(item: Any) -> list[dict[str, Any]]:
    locations = []
    for prov in getattr(item, "prov", None) or []:
        number = getattr(prov, "page_no", None)
        if not isinstance(number, int) or number < 1:
            # Cannot claim a PDF page anchor without a grounded page number.
            continue
        locations.append({
            "page": number,
            "bbox": _bbox(prov),
            "basis": "DOCLING_PDF_PROVENANCE",
        })
    return locations


def _extract_structural_candidates(document: Any) -> dict[str, Any]:
    pages = getattr(document, "pages", None)
    count = len(pages) if pages is not None else 0
    if not (1 <= count <= MAX_PAGES):
        raise ContractEvidenceParseError("invalid or excessive PDF page count")

    texts = list(getattr(document, "texts", []))
    tables = list(getattr(document, "tables", []))
    if len(texts) > MAX_TEXT_ITEMS:
        raise ContractEvidenceParseError("too many text items")
    if sum(len(getattr(getattr(t, "data", None), "table_cells", []) or []) for t in tables) > MAX_TABLE_CELLS:
        raise ContractEvidenceParseError("too many table cells")

    items: list[dict[str, Any]] = []
    pages_with_text: set[int] = set()
    pages_with_tables: set[int] = set()
    missing_page_anchors = 0

    for index, obj in enumerate(texts):
        body = str(getattr(obj, "text", "") or "").strip()
        if not body:
            continue
        locations = _locations(obj)
        if not locations:
            missing_page_anchors += 1
        else:
            pages_with_text.update(loc["page"] for loc in locations)
        items.append({
            "source_locator": f"docling:text:{index}",
            "kind": "text",
            "content": body,
            "document_label": str(getattr(obj, "label", "") or ""),
            "locations": locations,
            "review_state": "CANDIDATE_UNVALIDATED",
        })

    tab_items = []
    for index, obj in enumerate(tables):
        data = getattr(obj, "data", None)
        cells = getattr(data, "table_cells", []) or []
        locations = _locations(obj)
        if not locations:
            missing_page_anchors += 1
        else:
            pages_with_tables.update(loc["page"] for loc in locations)
        tab_items.append({
            "source_locator": f"docling:table:{index}",
            "kind": "table",
            "rows": int(getattr(data, "num_rows", 0)),
            "columns": int(getattr(data, "num_cols", 0)),
            "cells": [
                {
                    "text": str(getattr(cell, "text", "") or ""),
                    "row_start": getattr(cell, "start_row_offset_idx", None),
                    "col_start": getattr(cell, "start_col_offset_idx", None),
                }
                for cell in cells
            ],
            "locations": locations,
            "review_state": "CANDIDATE_UNVALIDATED",
        })
    # Never infer document order by concatenating texts and tables.
    # Docling's iterator preserves its parsed layout sequence (still requiring
    # visual QA before we call that sequence verified against the original).
    lookup: dict[str, str] = {}
    for index, obj in enumerate(texts):
        if str(getattr(obj, "text", "") or "").strip():
            lookup[str(getattr(obj, "self_ref", f"missing-text-{index}"))] = f"docling:text:{index}"
    for index, obj in enumerate(tables):
        lookup[str(getattr(obj, "self_ref", f"missing-table-{index}"))] = f"docling:table:{index}"
    order: list[str] = []
    found: set[str] = set()
    iterator = getattr(document, "iterate_items", None)
    if callable(iterator):
        try:
            for item, _level in iterator():
                locator = lookup.get(str(getattr(item, "self_ref", "")))
                if locator is not None and locator not in found:
                    order.append(locator)
                    found.add(locator)
        except Exception:
            # Honest failure: never guess a replacement text/table order.
            order = []
    order_complete = len(order) == len(items) + len(tab_items)
    if not order_complete:
        order = []

    anchors = pages_with_text | pages_with_tables
    return {
        "text_items": items,
        "tables": tab_items,
        "reading_order": order,
        "coverage": {
            "docling_layout_sequence_available": order_complete,
            "reading_order_verified_against_pdf": False,
            "pages_reported": count,
            "pages_with_grounded_text": sorted(pages_with_text),
            "pages_with_grounded_tables": sorted(pages_with_tables),
            "pages_without_grounded_content": [
                page for page in range(1, count + 1) if page not in anchors
            ],
            "text_item_count": len(items),
            "table_count": len(tab_items),
            "items_without_page_provenance": missing_page_anchors,
            "pdf_text_spans_verified_against_original": False,
            "clauses_analysed": False,
            "annex_coverage_complete": False,
        },
    }


def parse_verified_docling_candidates(
    *,
    source_bytes: bytes,
    expected_sha256: str,
    scope: DocumentEvidenceScope,
    document_kind: str,
    converter_factory: Callable[[], Any] | None = None,
    ocr_enabled: bool = False,
) -> dict[str, Any]:
    """Read one immutable PDF and expose provenance-rich structural *candidates*.

    The source SHA is verified before any conversion. No implicit inference,
    missing-annex fabrication, approval, WBS link or trusted promotion.
    """
    if not isinstance(scope, DocumentEvidenceScope):
        raise ContractEvidenceParseError("document evidence scope required")
    if document_kind not in DOCUMENT_KINDS:
        raise ContractEvidenceParseError("unsupported document kind")
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ContractEvidenceParseError("nonempty immutable PDF bytes required")
    if len(source_bytes) > MAX_PDF_BYTES:
        raise ContractEvidenceParseError("PDF byte size exceeds research limit")
    if not source_bytes.lstrip().startswith(b"%PDF-"):
        raise ContractEvidenceParseError("source does not appear to be PDF")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ContractEvidenceParseError("invalid revision checksum")
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if not hmac.compare_digest(source_sha, expected_sha256.lower()):
        raise ContractEvidenceParseError("pinned revision SHA256 mismatch")

    with tempfile.TemporaryDirectory(prefix="c2pro-docling-candidate-") as temp:
        path = Path(temp) / "source.pdf"
        path.write_bytes(source_bytes)
        converter = (converter_factory or (lambda: _make_docling_converter(ocr_enabled=ocr_enabled)))()
        try:
            converted = converter.convert(str(path), raises_on_error=False)
        except Exception as exc:
            raise ContractEvidenceParseError(
                f"document conversion failed ({type(exc).__name__})"
            ) from None

        doc = getattr(converted, "document", None)
        status = str(getattr(converted, "status", "UNKNOWN"))
        if doc is None or "SUCCESS" not in status.upper():
            raise ContractEvidenceParseError("Docling conversion did not finish successfully")
        structures = _extract_structural_candidates(doc)

    return {
        "scope": {
            "tenant_id": str(scope.tenant_id),
            "project_id": str(scope.project_id),
            "document_id": str(scope.document_id),
            "revision_id": str(scope.revision_id),
        },
        "source": {"format": ".pdf", "sha256": source_sha, "document_kind": document_kind,
                   "basis": "PINNED_SOURCE_BYTES", "parser": "docling"},
        "state": "CANDIDATE_UNVALIDATED",
        "trusted_promotions": 0,
        "effects_allowed": False,
        "contractual_assessment": "NOT_ASSESSED",
        **structures,
    }
