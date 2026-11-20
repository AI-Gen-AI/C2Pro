"""I-C01: real Docling smoke against generated synthetic contract + annex.

Do not point this script at private contracts without moving evidence into a
private workspace. Default inputs are strictly known synthetic PDF fixtures.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from uuid import UUID
import os
import sys
from src.documents.adapters.parsers.docling_contract_candidate_adapter import (
    DocumentEvidenceScope, _make_docling_converter, parse_verified_docling_candidates
)
from src.documents.adapters.parsers.docling_contract_window_packet import (
    build_untrusted_contract_windows,
)

lab = Path(os.getenv("C2PRO_OSS_LAB", Path.home() / "AppData" / "Local" / "AI-GEN" / "C2ProOSSResearch20261120"))
converter = _make_docling_converter(ocr_enabled=False)
inputs = [
    ("synthetic_contract.pdf", "contract", ["FAT", "950000", "9.6"]),
    ("synthetic_annex.pdf", "annex", ["WBS-130", "20 June 2027", "1030000"]),
]
results = []
for index, (filename, kind, expected) in enumerate(inputs, start=1):
    source = (lab / "fixtures" / filename).read_bytes()
    scope = DocumentEvidenceScope(
        tenant_id=UUID("1"*32), project_id=UUID("2"*32),
        document_id=UUID(str(index) * 32), revision_id=UUID("4"*32),
    )
    output = parse_verified_docling_candidates(
        source_bytes=source,
        expected_sha256=hashlib.sha256(source).hexdigest(),
        scope=scope,
        document_kind=kind,
        converter_factory=lambda: converter,
    )
    strings = " ".join(x["content"] for x in output["text_items"])
    strings += " " + " ".join(cell["text"] for table in output["tables"] for cell in table["cells"])
    present = {term: term.lower() in strings.lower() for term in expected}
    page_anchors = sum(len(x["locations"]) for x in output["text_items"] + output["tables"])
    packet = build_untrusted_contract_windows(output, max_chars=512)
    status = (
        "PASS"
        if all(present.values()) and page_anchors and output["trusted_promotions"] == 0
        and not output["effects_allowed"] and output["state"] == "CANDIDATE_UNVALIDATED"
        and packet["coverage"]["parsed_chars"] == packet["coverage"]["window_chars"]
        and packet["trusted_promotions"] == 0 and not packet["n4_executed"]
        and all(len(w["text"]) <= 512 for w in packet["windows"])
        else "FAIL"
    )
    results.append({
        "file": filename, "kind": kind, "status": status, "expected_term_presence": present,
        "pages": output["coverage"]["pages_reported"],
        "tables": output["coverage"]["table_count"],
        "text_items": output["coverage"]["text_item_count"],
        "anchored_items": page_anchors,
        "unanchored_items": output["coverage"]["items_without_page_provenance"],
        "pages_without_grounded_content": output["coverage"]["pages_without_grounded_content"],
        "trusted_promotions": output["trusted_promotions"],
        "context_windows": packet["coverage"]["window_count"],
        "window_chars_preserved": packet["coverage"]["window_chars"],
        "window_input_chars": packet["coverage"]["parsed_chars"],
        "n4_executed": packet["n4_executed"],
    })
report = {
    "study": "I-C01 Docling native isolated integration",
    "synthetic_only": True,
    "status": "PASS" if all(x["status"] == "PASS" for x in results) else "FAIL",
    "results": results,
    "limitations": [
      "Source page anchors and bbox are Docling estimates; not yet visually audited against original PDF.",
      "Presence of a string or clause number is NOT correct contractual interpretation.",
      "No N4/N12, HITL, ProjectGraph, baseline comparison, approved risk or legal oracle was executed.",
      "No changes to C2Pro upload router, existing PDFFileParser or database.",
    ],
}
output_path = lab / "results" / "docling_contract_adapter_native_smoke.json"
output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
sys.exit(0 if report["status"] == "PASS" else 2)
