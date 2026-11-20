"""B0 option: retain legacy PDF text for N2/N4; add Docling tables as sidecar.

Docling may expose tables and page boxes even when its iterate_items() does
not include all text. Never replace baseline text with incomplete Docling
content; missing pages, coordinates and layout order are made explicit.

NOT a live plugin, N4 input, N12 attestation, original-source certificate,
approval action or ProjectGraph write.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any


class SidecarEvidenceError(ValueError):
    """Invalid pairing of baseline source text and optional Docling evidence."""


def build_optional_table_sidecar(
    *,
    physical_pdf_sha256: str,
    baseline_blocks: list[dict[str, Any]],
    total_pdf_pages: int,
    docling_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(physical_pdf_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}",physical_pdf_sha256):
        raise SidecarEvidenceError("physical PDF SHA required")
    if not isinstance(total_pdf_pages,int) or not (1 <= total_pdf_pages <= 300):
        raise SidecarEvidenceError("PDF page count invalid")
    pieces: list[str] = []
    text_pages: set[int] = set()
    block_refs: list[dict[str, Any]] = []
    cursor = 0
    for block in baseline_blocks:
        body = block.get("text")
        page = block.get("page")
        if not isinstance(body,str) or not body.strip():
            continue
        if not isinstance(page,int) or not (1 <= page <= total_pdf_pages):
            raise SidecarEvidenceError("baseline text block has invalid page")
        if pieces:
            pieces.append("\n\n")
            cursor += 2
        start = cursor
        cursor += len(body)
        pieces.append(body)
        text_pages.add(page)
        block_refs.append({"page":page,"source_start":start,
                           "source_end":cursor,"bbox":block.get("bbox")})
    full_text="".join(pieces)
    if not full_text.strip():
        raise SidecarEvidenceError("legacy parser found no text")
    output={
        "physical_pdf_sha256":physical_pdf_sha256.lower(),
        "baseline_text":full_text,
        "baseline_text_sha256":hashlib.sha256(full_text.encode()).hexdigest(),
        "baseline_block_spans":block_refs,
        "baseline_text_pages":sorted(text_pages),
        "pages_without_baseline_text":[p for p in range(1,total_pdf_pages+1) if p not in text_pages],
        "source_of_n2_text":"CURRENT_PDF_PARSER",
        "docling_table_status":"UNAVAILABLE",
        "docling_layout_sequence_verified":False,
        "docling_tables":[],
        "docling_extra_text_accepted_into_n2":False,
        "n2_redaction_map_available":False,
        "n4_executed":False,
        "n12_attestation":None,
        "trusted_promotions":0,
    }
    if docling_candidate is None:
        return output
    if docling_candidate.get("state")!="CANDIDATE_UNVALIDATED" or docling_candidate.get("trusted_promotions")!=0:
        raise SidecarEvidenceError("Docling evidence must remain untrusted")
    other=docling_candidate.get("source",{}).get("sha256")
    if not isinstance(other,str) or not hmac.compare_digest(other.lower(),physical_pdf_sha256.lower()):
        raise SidecarEvidenceError("Docling sidecar is not from identical PDF bytes")
    coverage=docling_candidate.get("coverage",{})
    if coverage.get("pages_reported")!=total_pdf_pages:
        raise SidecarEvidenceError("Docling parser page-count mismatch")
    structured=[]
    for table in docling_candidate.get("tables",[]):
        pages=sorted({entry.get("page") for entry in table.get("locations",[])
                      if isinstance(entry.get("page"),int)})
        if not pages or any(p<1 or p>total_pdf_pages for p in pages):
            continue
        # Keep row/column cell structure. No injection into baseline text.
        structured.append({
            "source_locator":table.get("source_locator"),
            "pages":pages,
            "bbox": [entry.get("bbox") for entry in table.get("locations",[])],
            "rows":table.get("rows"),
            "columns":table.get("columns"),
            "cells":table.get("cells",[]),
            "status":"ADVISORY_UNVERIFIED",
        })
    output.update({
        "docling_table_status":"ADVISORY_ONLY",
        "docling_layout_sequence_verified":False,
        "docling_tables":structured,
        "docling_tables_without_page_locator":len(docling_candidate.get("tables",[]))-len(structured),
        "docling_raw_order_complete":bool(coverage.get("docling_layout_sequence_available")),
    })
    return output
