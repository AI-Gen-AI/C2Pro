"""Pure unit tests: Docling enriches, never replaces, baseline N4 source."""
import hashlib
import unittest

from src.documents.adapters.parsers.docling_optional_table_sidecar import (
    SidecarEvidenceError, build_optional_table_sidecar,
)

HASH=hashlib.sha256(b"synthetic pdf bytes").hexdigest()
BLOCKS=[
    {"text":"Clause 9.6 deadline", "page":1, "bbox":(0,0,10,10)},
    {"text":"Annex C referenced", "page":3, "bbox":(1,1,11,11)},
]
DOC={
  "state":"CANDIDATE_UNVALIDATED",
  "trusted_promotions":0,
  "source":{"sha256":HASH},
  "coverage":{"pages_reported":3,"docling_layout_sequence_available":False},
  "tables":[{"source_locator":"docling:table:3","rows":2,"columns":2,
     "locations":[{"page":2,"bbox":[0,0,100,100]}],
     "cells":[{"row_start":0,"col_start":0,"text":"Date"},
              {"row_start":0,"col_start":1,"text":"Value"},
              {"row_start":1,"col_start":0,"text":"May"},
              {"row_start":1,"col_start":1,"text":"100"}]}],
}

class SidecarTests(unittest.TestCase):
    def test_legacy_text_retained_despite_incomplete_docling_order(self):
        o=build_optional_table_sidecar(
            physical_pdf_sha256=HASH,baseline_blocks=BLOCKS,total_pdf_pages=3,
            docling_candidate=DOC)
        self.assertEqual(o["baseline_text"],"Clause 9.6 deadline\n\nAnnex C referenced")
        self.assertEqual(o["pages_without_baseline_text"],[2])
        self.assertEqual(o["docling_table_status"],"ADVISORY_ONLY")
        self.assertFalse(o["docling_raw_order_complete"])
        self.assertEqual(o["docling_tables"][0]["pages"],[2])
        self.assertEqual(o["docling_tables"][0]["cells"][3]["text"],"100")
        self.assertFalse(o["docling_extra_text_accepted_into_n2"])
        self.assertEqual(o["trusted_promotions"],0)
        self.assertFalse(o["n4_executed"])
        self.assertIsNone(o["n12_attestation"])

    def test_without_docling_is_allowed_without_erasing_text(self):
        o=build_optional_table_sidecar(
            physical_pdf_sha256=HASH,baseline_blocks=BLOCKS,total_pdf_pages=3)
        self.assertEqual(o["docling_table_status"],"UNAVAILABLE")
        self.assertTrue(o["baseline_text"])
        self.assertEqual(o["docling_tables"],[])

    def test_cannot_mix_document_revisions(self):
        d={**DOC,"source":{"sha256":"0"*64}}
        with self.assertRaisesRegex(SidecarEvidenceError,"identical PDF"):
            build_optional_table_sidecar(physical_pdf_sha256=HASH,
                baseline_blocks=BLOCKS,total_pdf_pages=3,docling_candidate=d)

    def test_rejects_wrong_page_count(self):
        d={**DOC,"coverage":{"pages_reported":2}}
        with self.assertRaisesRegex(SidecarEvidenceError,"page-count"):
            build_optional_table_sidecar(physical_pdf_sha256=HASH,
                baseline_blocks=BLOCKS,total_pdf_pages=3,docling_candidate=d)

    def test_only_page_grounded_tables_enter_sidecar(self):
        d={**DOC,"tables":[
            {**DOC["tables"][0],"locations":[]},
            DOC["tables"][0],
        ]}
        o=build_optional_table_sidecar(physical_pdf_sha256=HASH,
            baseline_blocks=BLOCKS,total_pdf_pages=3,docling_candidate=d)
        self.assertEqual(len(o["docling_tables"]),1)
        self.assertEqual(o["docling_tables_without_page_locator"],1)

    def test_no_empty_baseline_or_invalid_page_is_accepted(self):
        with self.assertRaisesRegex(SidecarEvidenceError,"no text"):
            build_optional_table_sidecar(physical_pdf_sha256=HASH,
                baseline_blocks=[],total_pdf_pages=3)
        with self.assertRaisesRegex(SidecarEvidenceError,"invalid page"):
            build_optional_table_sidecar(physical_pdf_sha256=HASH,
                baseline_blocks=[{"text":"X","page":4}],total_pdf_pages=3)

if __name__=="__main__":
    unittest.main()
