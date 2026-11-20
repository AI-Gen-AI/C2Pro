"""Docling contract candidate adapter: synthetic-only unit tests (no OCR/models)."""
from __future__ import annotations

import hashlib
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from uuid import UUID

from src.documents.adapters.parsers.docling_contract_candidate_adapter import (
    ContractEvidenceParseError, DocumentEvidenceScope, parse_verified_docling_candidates,
)


SCOPE = DocumentEvidenceScope(
    tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
    project_id=UUID("22222222-2222-2222-2222-222222222222"),
    document_id=UUID("33333333-3333-3333-3333-333333333333"),
    revision_id=UUID("44444444-4444-4444-4444-444444444444"),
)
DATA = b"%PDF-1.4\n%synthetic fixture\n"


def fake_document(anchor=True):
    bbox = NS(l=10.0, t=20.0, r=30.0, b=40.0)
    prov = [NS(page_no=1, bbox=bbox)] if anchor else []
    clause = NS(text="Clause 9.6 FAT deadline 2027-05-30",
                label="text", prov=prov, self_ref="#/texts/0")
    table = NS(data=NS(num_rows=1, num_cols=2, table_cells=[
            NS(text="WBS", start_row_offset_idx=0, start_col_offset_idx=0),
            NS(text="WBS-100", start_row_offset_idx=0, start_col_offset_idx=1),
        ]), prov=prov, self_ref="#/tables/0")
    return NS(
        pages={1: NS(), 2: NS()},
        texts=[clause], tables=[table],
        iterate_items=lambda: iter([(clause, 1), (table, 1)]),
    )


def execute(document=None, *, converter=None, src=DATA, sha=None, kind="contract"):
    if converter is None:
        converter = NS(convert=lambda path, raises_on_error: NS(status="SUCCESS",
                                                                document=document or fake_document()))
    return parse_verified_docling_candidates(
        source_bytes=src, expected_sha256=sha or hashlib.sha256(src).hexdigest(),
        scope=SCOPE, document_kind=kind, converter_factory=lambda: converter
    )


class DoclingContractAdapterTests(unittest.TestCase):
    def test_candidate_with_page_bbox_table_cells_and_scope(self):
        result = execute()
        self.assertEqual(result["scope"]["revision_id"], str(SCOPE.revision_id))
        self.assertEqual(result["source"]["document_kind"], "contract")
        self.assertEqual(result["state"], "CANDIDATE_UNVALIDATED")
        self.assertEqual(result["contractual_assessment"], "NOT_ASSESSED")
        self.assertEqual(result["trusted_promotions"], 0)
        self.assertFalse(result["effects_allowed"])
        self.assertEqual(result["text_items"][0]["locations"][0]["page"], 1)
        self.assertEqual(result["text_items"][0]["locations"][0]["bbox"], [10,20,30,40])
        self.assertEqual(result["tables"][0]["rows"], 1)
        self.assertEqual(result["tables"][0]["cells"][1]["text"], "WBS-100")
        self.assertEqual(result["coverage"]["pages_without_grounded_content"], [2])
        self.assertFalse(result["coverage"]["annex_coverage_complete"])
        self.assertEqual(result["reading_order"], ["docling:text:0", "docling:table:0"])
        self.assertTrue(result["coverage"]["docling_layout_sequence_available"])

    def test_pinned_sha_checked_before_converter_instantiation(self):
        called = []
        with self.assertRaisesRegex(ContractEvidenceParseError, "SHA256 mismatch"):
            parse_verified_docling_candidates(
                source_bytes=DATA, expected_sha256="0" * 64, scope=SCOPE,
                document_kind="contract", converter_factory=lambda: called.append(1)
            )
        self.assertEqual(called, [])

    def test_rejects_non_pdf_and_empty_source(self):
        with self.assertRaisesRegex(ContractEvidenceParseError, "does not appear"):
            execute(src=b"hello")
        with self.assertRaisesRegex(ContractEvidenceParseError, "nonempty"):
            execute(src=b"")

    def test_rejects_unsupported_document_kinds(self):
        with self.assertRaisesRegex(ContractEvidenceParseError, "document kind"):
            execute(kind="approved_contract")
        self.assertEqual(execute(kind="annex")["source"]["document_kind"], "annex")

    def test_rejects_absent_scope(self):
        with self.assertRaisesRegex(ContractEvidenceParseError, "scope"):
            parse_verified_docling_candidates(
                source_bytes=DATA, expected_sha256=hashlib.sha256(DATA).hexdigest(),
                scope=None, document_kind="contract", converter_factory=lambda: None
            )

    def test_without_anchor_reports_no_grounded_pages(self):
        result = execute(fake_document(anchor=False))
        self.assertEqual(result["coverage"]["items_without_page_provenance"], 2)
        self.assertEqual(result["coverage"]["pages_without_grounded_content"], [1, 2])
        self.assertEqual(result["tables"][0]["locations"], [])

    def test_conversion_failure_does_not_expose_source(self):
        converter = NS(convert=lambda path, raises_on_error: (_ for _ in ()).throw(
            RuntimeError("secret contract 550012")))
        with self.assertRaises(ContractEvidenceParseError) as caught:
            execute(converter=converter)
        self.assertNotIn("secret contract", str(caught.exception))

    def test_incomplete_conversion_fails_closed(self):
        with self.assertRaisesRegex(ContractEvidenceParseError, "did not finish"):
            execute(converter=NS(convert=lambda path, raises_on_error:
                                 NS(status="PARTIAL_SUCCESS", document=None)))

    def test_temp_file_removed_after_conversion(self):
        seen=[]
        def convert(path, raises_on_error):
            from pathlib import Path
            seen.append(path)
            self.assertEqual(Path(path).read_bytes(), DATA)
            return NS(status="SUCCESS", document=fake_document())
        execute(converter=NS(convert=convert))
        from pathlib import Path
        self.assertFalse(Path(seen[0]).exists())

    def test_size_guard_without_large_data_allocation(self):
        with patch("src.documents.adapters.parsers.docling_contract_candidate_adapter.MAX_PDF_BYTES", 10):
            with self.assertRaisesRegex(ContractEvidenceParseError, "size"):
                execute()

    def test_pages_limit_and_table_cells_limit(self):
        too_many_pages = NS(pages={i:NS() for i in range(1,302)}, texts=[], tables=[])
        with self.assertRaisesRegex(ContractEvidenceParseError, "page count"):
            execute(too_many_pages)
        with patch("src.documents.adapters.parsers.docling_contract_candidate_adapter.MAX_TABLE_CELLS", 1):
            with self.assertRaisesRegex(ContractEvidenceParseError, "too many table cells"):
                execute()

    def test_no_output_implies_no_trusted_promotion_even_with_content(self):
        result = execute()
        self.assertNotIn("coherence_score", result)
        self.assertNotIn("projectgraph_state", result)
        self.assertTrue(all(x["review_state"] == "CANDIDATE_UNVALIDATED" for x in result["text_items"]))


if __name__ == "__main__":
    unittest.main()
