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
            {"source_locator":"docling:text:0","content":"A"*400,
             "locations":[{"page":1}]},
            {"source_locator":"docling:text:1","content":"B"*250,
             "locations":[{"page":2}]},
            {"source_locator":"docling:text:2","content":"UNANCHORED",
             "locations":[]},
        ],
        "tables": [
            {"source_locator":"docling:table:0",
             "cells":[{"text":"x","row_start":0,"col_start":0},
                      {"text":"y","row_start":0,"col_start":1}],
             "locations":[{"page":2}]},
        ],
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
        with self.assertRaisesRegex(ContractWindowError, "no parsed"):
            build_untrusted_contract_windows(source)

    def test_rejects_invalid_bound(self):
        with self.assertRaisesRegex(ContractWindowError, "bound"):
            build_untrusted_contract_windows(candidate(), max_chars=40_001)

    def test_splits_oversized_blocks_with_no_holes(self):
        source = candidate()
        source["text_items"] = [{
            "source_locator":"docling:text:0","content":"Z"*1200,
            "locations":[{"page":1}]}]
        source["tables"] = []
        output = build_untrusted_contract_windows(source, max_chars=256)
        reassembled = "".join(w["text"] for w in output["windows"])
        self.assertEqual(reassembled, "Z"*1200)
        self.assertEqual(len(output["windows"]), 5)


if __name__ == "__main__":
    unittest.main()
