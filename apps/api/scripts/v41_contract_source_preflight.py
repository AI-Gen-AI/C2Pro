"""Read a public SEC EPC PDF with the real C2Pro PDF parser and N2.

PRE-FLIGHT ONLY. Never calls a model, writes application state, or claims UAT.
Source PDF from 8-K has 224 pages; exhibit 99.1 occupies source pages 4-76.
This 73-page PDF rendition is NOT the originally uploaded 94-page PDF.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json

from scripts.v41_private_cli_paths import authorize_runner_sec_paths
from pathlib import Path

import fitz

from src.analysis.adapters.graph.nodes_extended import pii_anonymizer_node
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.adapters.parsers.source_inventory import inspect_pdf_source_inventory

EXPECTED_SEC_PDF_SHA256 = "2370812124b5f42713153122fc45f1e5716dd85385d881bdd339bd87b9dced06"
EXPECTED_EXHIBIT_SHA256 = "0b1445eee7bab1780bff00e2e1e0a0bbfc231a9f625d8643a4241b6141e1d58a"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def preflight(sec_pdf: Path, out_dir: Path) -> dict:
    if sha256(sec_pdf) != EXPECTED_SEC_PDF_SHA256:
        raise RuntimeError("SEC_PDF_SHA256_MISMATCH")
    if not out_dir.is_dir() or out_dir.is_symlink():
        raise RuntimeError("PINNED_SEC_OUTPUT_DIR_NOT_AVAILABLE")
    with fitz.open(sec_pdf) as filing:
        if filing.page_count != 224:
            raise RuntimeError("SEC_PDF_PAGE_COUNT_CHANGED")
        if "EXHIBIT 99.1" not in filing[3].get_text():
            raise RuntimeError("SEC_EX991_START_NOT_FOUND")
        if "EXHIBIT 99.2" not in filing[76].get_text():
            raise RuntimeError("SEC_EX992_BOUNDARY_NOT_FOUND")
        with fitz.open() as exhibit:
            exhibit.insert_pdf(filing, from_page=3, to_page=75)
            pdf = out_dir / "solarmax_ex991_73page_sec_rendition.pdf"
            exhibit.save(pdf, garbage=4, deflate=True)
    # PyMuPDF may regenerate PDF object IDs or metadata across executions.
    # Authenticate the original filing hash and page boundary; report the
    # derived PDF hash actually produced instead of pinning its serialization.
    derived_pdf_sha256 = sha256(pdf)
    blocks = await PDFFileParser().extract_text_and_offsets(pdf)
    coverage = inspect_pdf_source_inventory(pdf, blocks)
    if coverage.get("source_pages") != 73 or coverage.get("pages_without_extracted_text"):
        raise RuntimeError("SOURCE_PAGE_COVERAGE_INCOMPLETE")

    pages: dict[int, list[str]] = {}
    for block in blocks:
        pages.setdefault(block["page"], []).append(block["text"])
    if sorted(pages) != list(range(1, 74)):
        raise RuntimeError("SOURCE_PAGE_TRACE_INCOMPLETE")
    source = "".join(
        f"\n\n[[PDF_PAGE_{p:03d} SEC_8K_PAGE_{p + 3:03d}]]\n"
        + "\n".join(pages[p])
        for p in range(1, 74)
    )
    state = {
        "document_text": source,
        "anonymized_text": "",
        "pii_anonymization_complete": False,
        "messages": [],
        "node_results": [],
        "project_id": "isolated-source-preflight",
    }
    result = await pii_anonymizer_node(state)
    if result.get("pii_anonymization_complete") is not True:
        raise RuntimeError("N2_PII_DID_NOT_COMPLETE")
    safe = result["anonymized_text"]
    for page in range(1, 74):
        if f"[[PDF_PAGE_{page:03d}" not in safe:
            raise RuntimeError("N2_PAGE_TRACE_LOST")
    windows = plan_n4_source_windows(
        safe, revision_id="naguabo-epc-sec-ex991-public-v1"
    )
    if "".join(w.core_text for w in windows) != safe:
        raise RuntimeError("N4_WINDOW_COVERAGE_GAP")
    result_json = {
        "source_filing_sha256": EXPECTED_SEC_PDF_SHA256,
        "source_exhibit_sha256": derived_pdf_sha256,
        "source_filing_pages": 224,
        "source_exhibit_pages": 73,
        "original_library_pdf_pages": 94,
        "original_library_pdf_is_same_file": False,
        "n1_observed_pages": len(pages),
        "n1_text_blocks": len(blocks),
        "n1_text_chars": len(source),
        "n1_text_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "n1_unextractable_pages": coverage["pages_without_extracted_text"],
        "n1_limitations": coverage["limitations"],
        "n2_text_chars": len(safe),
        "n2_text_sha256": hashlib.sha256(safe.encode()).hexdigest(),
        "n2_redactions": len(result["pii_redactions"]),
        "n4_windows_planned": len(windows),
        "n4_chars_covered_exactly_once": sum(len(w.core_text) for w in windows),
        "n4_context_chars_total": sum(w.context_chars for w in windows),
        "n4_window_core_sha256": [
            hashlib.sha256(w.core_text.encode()).hexdigest() for w in windows
        ],
        "n4_model_examined_windows": 0,
        "provider_calls": 0,
        "status": "PREPARED_NOT_AI_UAT",
    }
    (out_dir / "preflight_sanitized.json").write_text(
        json.dumps(result_json, indent=2), encoding="utf-8"
    )
    # The source projection may contain confidential information in other
    # corpora. This public-only sample is kept job-private, never uploaded.
    (out_dir / "source_n2_protected.txt").write_text(safe, encoding="utf-8")
    return result_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sec-pdf", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    locked_pdf, locked_out = authorize_runner_sec_paths(
        args.sec_pdf, args.out_dir, stage="source",
    )
    answer = asyncio.run(preflight(locked_pdf, locked_out))
    print(json.dumps(
        {k: v for k, v in answer.items() if k != "n4_window_core_sha256"},
        indent=2,
    ))
