"""Pure offline tests for Docling→N4 candidate window packet. No LLM calls."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from src.documents.adapters.parsers.docling_contract_window_packet import (
    ContractWindowError, build_untrusted_contract_windows,
)


def candidate():
    return {
        "scope": {"tenant_id":"t","project_id":"p","document_id":"d","revision_id":"r"},
        "source": {"basis":"PINNED_SOURCE_BYTES","sha256":"abc","format":".pdf"},
        "state": "CANDIDATE_UNVALIDATED",
        "trusted_promotions": 0,
        "effects_allowed": False,
        "text_items": [
            {"source_locator":"docling:text:0","content":"A "*200,
             "locations":[{"page":1}]},
            {"source_locator":"docling:text:1","content":"B "*125,
             "locations":[{"page":2}]},
            {"source_locator":"docling:text:2","content":"UNANCHORED",
             "locations":[]},
        ],
        "tables": [
            {"source_locator":"docling:table:0",
             "rows":1, "columns":2,
             "cells":[{"text":"x","row_start":0,"col_start":0},
                      {"text":"y","row_start":0,"col_start":1}],
             "locations":[{"page":2}]},
        ],
        "reading_order": ["docling:text:0", "docling:table:0", "docling:text:1", "docling:text:2"],
    }


class ContractWindowPacketTests(unittest.TestCase):
    def test_conserves_all_characters_and_keeps_source_offsets(self):
        source = candidate()
        result = build_untrusted_contract_windows(source, max_chars=256)
        self.assertEqual(result["coverage"]["parsed_chars"], 665)
        self.assertEqual(result["coverage"]["window_chars"], 665)
        self.assertEqual(result["coverage"]["window_count"], 3)
        self.assertEqual(result["coverage"]["unanchored_segments"], 1)
        self.assertEqual(result["windows"][0]["parts"][0]["source_start"], 0)
        self.assertEqual(result["windows"][1]["parts"][0]["source_start"], 256)
        self.assertTrue(all(len(x["text"]) <= 256 for x in result["windows"]))
        self.assertTrue(all(x["state"] == "CANDIDATE_UNVALIDATED" for x in result["windows"]))

    def test_never_claims_n12_or_pdf_attestation(self):
        result = build_untrusted_contract_windows(candidate(), max_chars=512)
        self.assertFalse(result["n4_executed"])
        self.assertFalse(result["n12_executed"])
        self.assertIsNone(result["n12_source_attestation"])
        self.assertEqual(result["original_pdf_attestation"], "UNVERIFIED")
        self.assertEqual(result["trusted_promotions"], 0)
        self.assertFalse(result["effects_allowed"])
        self.assertFalse(result["coverage"]["reading_order_verified"])

    def test_disallows_untrusted_packet_with_effects_enabled(self):
        source = candidate()
        source["effects_allowed"] = True
        with self.assertRaisesRegex(ContractWindowError, "unsafe"):
            build_untrusted_contract_windows(source)

    def test_rejects_no_pinned_source(self):
        source = candidate()
        source["source"]["basis"] = "MUTABLE"
        with self.assertRaisesRegex(ContractWindowError, "not pinned"):
            build_untrusted_contract_windows(source)

    def test_empty_packet_fails(self):
        source = candidate()
        source["text_items"] = []
        source["tables"] = []
        source["reading_order"] = []
        with self.assertRaisesRegex(ContractWindowError, "no parsed"):
            build_untrusted_contract_windows(source)

    def test_rejects_invalid_bound(self):
        with self.assertRaisesRegex(ContractWindowError, "bound"):
            build_untrusted_contract_windows(candidate(), max_chars=40_001)

    def test_splits_oversized_blocks_with_no_holes(self):
        source = candidate()
        source["text_items"] = [{
            "source_locator":"docling:text:0","content":"Z "*600,
            "locations":[{"page":1}]}]
        source["tables"] = []
        source["reading_order"] = ["docling:text:0"]
        output = build_untrusted_contract_windows(source, max_chars=256)
        reassembled = "".join(w["text"] for w in output["windows"])
        self.assertEqual(reassembled, "Z "*600)
        self.assertEqual(len(output["windows"]), 5)

    def test_unbreakable_large_token_fails_instead_of_silent_split(self):
        source = candidate()
        source["text_items"] = [{"source_locator":"docling:text:0",
            "content":"X"*600,"locations":[{"page":1}]}]
        source["tables"] = []
        source["reading_order"] = ["docling:text:0"]
        with self.assertRaisesRegex(ContractWindowError, "unbreakable"):
            build_untrusted_contract_windows(source, max_chars=256)

    def test_table_rows_and_native_layout_are_preserved(self):
        source = candidate()
        source["tables"][0]["rows"] = 2
        source["tables"][0]["cells"].extend([
            {"text":"total","row_start":1,"col_start":0},
            {"text":"500","row_start":1,"col_start":1},
        ])
        source["tables"][0]["locations"] = [{"page":2}, {"page":3}]
        result = build_untrusted_contract_windows(source, max_chars=512)
        pieces = [p for window in result["windows"] for p in window["parts"]]
        table = [p for p in pieces if p["kind"] == "table_projection"]
        self.assertEqual(len(table), 1)
        self.assertEqual(table[0]["pages"], [2, 3])
        self.assertIn("x | y\ntotal | 500", table[0]["text"])
        text = "".join(w["text"] for w in result["windows"])
        self.assertLess(text.index("x | y"), text.index("B B "))

    def test_fails_when_docling_reading_order_is_missing(self):
        source = candidate()
        source.pop("reading_order")
        with self.assertRaisesRegex(ContractWindowError, "reading order"):
            build_untrusted_contract_windows(source, max_chars=512)


if __name__ == "__main__":
    unittest.main()
