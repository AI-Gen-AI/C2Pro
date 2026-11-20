"""B0: compare C2Pro legacy PDF parser and optional Docling on identical PDF bytes.

Offline only, no LLM, no database, no production calls, no private documents.
Usage: PYTHONPATH=apps/api python benchmark_docling_vs_legacy_public_pdf.py
       --name Longfellow_SEC_PUBLIC_RENDER.pdf
Source PDFs must be created/downloaded from a PUBLIC source or be synthetic.
The Longfellow file is a CHROME-PRINTED DERIVATIVE of an official SEC HTML:
its page coordinates are not SEC original PDF pages.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from uuid import UUID

from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.adapters.parsers.docling_contract_candidate_adapter import (
    ContractEvidenceParseError,
    DocumentEvidenceScope,
    parse_verified_docling_candidates,
)
from src.documents.adapters.parsers.docling_contract_window_packet import (
    ContractWindowError,
    _text_segments,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows

SAFE_FILES = frozenset({
    "synthetic_contract.pdf",
    "synthetic_annex.pdf",
    "Longfellow_SEC_PUBLIC_RENDER.pdf",
})
MARKERS = {
    "section_2_5_5": r"2\s*\.\s*5\s*\.\s*5",
    "section_9_6": r"\b9\s*\.\s*6\b",
    "section_4_3_1": r"4\s*\.\s*3\s*\.\s*1",
    "article_13": r"\b(?:article\s+)?13\s*[.:\-]",
    "exhibit_C": r"\b(?:exhibit|annex)\s+C\b",
    "exhibit_D": r"\b(?:exhibit|annex)\s+D\b",
    "fat": r"\bFAT\b",
}

def summarize_markers(text: str) -> dict[str, bool]:
    return {key: bool(re.search(pattern, text, re.I)) for key, pattern in MARKERS.items()}

async def compare(path: Path, result_dir: Path) -> dict:
    source = path.read_bytes()
    source_sha = hashlib.sha256(source).hexdigest()
    result = {
        "status": "PASS_LIMITED",
        "name": path.name,
        "public_or_synthetic_only": True,
        "source_sha256": source_sha,
        "pdf_bytes": len(source),
        "source_warning": "SEC PDF was printed locally from public HTML; not an SEC-issued PDF"
                          if path.name.startswith("Longfellow") else "Synthetic fixture only",
        "limitations": [
            "Structural marker presence is not contractual recall, precision or legal analysis",
            "PDF page citation identity is not attested against the original SEC HTML or signed PDF",
            "No N2 PII projection, N4 provider, N12, ProjectGraph, HITL or Score is invoked",
            "Docling table count is not verified 2D cell accuracy; legacy parser has no table API",
            "N4 window plan only: its existence does not mean windows were examined by a model",
        ],
    }
    start = time.perf_counter()
    try:
        parser = PDFFileParser(ocr_language="eng")
        baseline = await parser.extract_text_and_offsets(path)
        baseline_text = "\n\n".join(x["text"] for x in baseline)
        baseline_pages = sorted({int(x.get("page")) for x in baseline if x.get("page")})
        result["baseline"] = {
            "status": "PASS", "seconds": round(time.perf_counter()-start, 3),
            "text_chars": len(baseline_text),
            "text_blocks": len(baseline),
            "anchored_pages": len(baseline_pages),
            "pages": baseline_pages,
            "ocr_diagnostics": list(getattr(baseline, "ocr_diagnostics", [])),
            "markers": summarize_markers(baseline_text),
            "source_text_sha256": hashlib.sha256(baseline_text.encode()).hexdigest(),
        }
        baseline_windows = plan_n4_source_windows(
            baseline_text, revision_id="public-or-synthetic",
            max_context_chars=12_000, overlap_chars=400,
        )
        result["baseline"]["n4_window_plan"] = {
            "windows": len(baseline_windows),
            "core_chars": sum(len(w.core_text) for w in baseline_windows),
            "all_chars_preserved": "".join(w.core_text for w in baseline_windows) == baseline_text,
        }
    except Exception as exc:
        result["baseline"] = {"status": "FAIL", "error_type": type(exc).__name__,
                              "error": str(exc)[:240]}

    start = time.perf_counter()
    try:
        scope = DocumentEvidenceScope(
            tenant_id=UUID("1"*32), project_id=UUID("2"*32),
            document_id=UUID("3"*32), revision_id=UUID("4"*32),
        )
        candidate = parse_verified_docling_candidates(
            source_bytes=source, expected_sha256=source_sha,
            scope=scope, document_kind="contract", ocr_enabled=False,
        )
        info = candidate["coverage"]
        details = {
            "status": "PASS", "seconds": round(time.perf_counter()-start, 3),
            "pages_reported": info["pages_reported"],
            "text_items": info["text_item_count"],
            "tables": info["table_count"],
            "table_cells": sum(len(t["cells"]) for t in candidate["tables"]),
            "unanchored_items": info["items_without_page_provenance"],
            "pages_without_grounded_content": info["pages_without_grounded_content"],
            "layout_sequence_complete": info["docling_layout_sequence_available"],
            "trusted_promotions": candidate["trusted_promotions"],
        }
        if info["docling_layout_sequence_available"]:
            segments = _text_segments(candidate)
            text_projection = "\n\n".join(x["text"] for x in segments)
            windows = plan_n4_source_windows(
                text_projection, revision_id="public-or-synthetic",
                max_context_chars=12_000, overlap_chars=400,
            )
            details.update({
                "text_projection_chars": len(text_projection),
                "source_text_sha256": hashlib.sha256(text_projection.encode()).hexdigest(),
                "markers": summarize_markers(text_projection),
                "n4_window_plan": {
                    "windows": len(windows),
                    "core_chars": sum(len(w.core_text) for w in windows),
                    "all_chars_preserved": "".join(w.core_text for w in windows) == text_projection,
                    "overlap_chars": 400,
                },
                "candidate_page_spans_present": bool(
                    info["pages_with_grounded_text"] or info["pages_with_grounded_tables"]),
            })
        else:
            details["status"] = "PASS_LIMITED"
            details["reason"] = "Docling reading order incomplete; cannot feed N4 safely"
        result["docling"] = details
    except Exception as exc:
        result["docling"] = {"status": "FAIL", "seconds": round(time.perf_counter()-start,3),
                             "error_type": type(exc).__name__, "error": str(exc)[:240]}
    if "FAIL" in (result["baseline"]["status"], result["docling"]["status"]):
        result["status"] = "FAIL"
    elif result["docling"]["status"] == "PASS_LIMITED":
        result["status"] = "PASS_LIMITED"
    result_dir.mkdir(parents=True, exist_ok=True)
    dest = result_dir / ("B0_" + path.stem + ".json")
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "filename": path.name,
        "baseline": {k:v for k,v in result["baseline"].items() if k in
                     ("status","seconds","text_chars","text_blocks","anchored_pages","n4_window_plan","error")},
        "docling": {k:v for k,v in result["docling"].items() if k in
                    ("status","seconds","pages_reported","tables","table_cells","unanchored_items",
                     "layout_sequence_complete","text_projection_chars","n4_window_plan","reason","error")},
        "report": str(dest),
    }, ensure_ascii=False))
    return result

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", choices=sorted(SAFE_FILES), required=True)
    ap.add_argument("--lab", type=Path, default=Path.home()/ "AppData"/ "Local"/ "AI-GEN"/ "C2ProOSSResearch20261120")
    ns = ap.parse_args()
    v = asyncio.run(compare(ns.lab/"fixtures"/ns.name,ns.lab/"results"))
    sys.exit(0 if v["status"] in ("PASS","PASS_LIMITED") else 2)
