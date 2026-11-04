"""Behavioral checks for the focused real-AI N4→N12 evaluation runner."""

from __future__ import annotations

import unittest

from scripts import n4_n12_real_ai_eval as runner


class TestN4N12RealAiEval(unittest.TestCase):
    def test_n4_metrics_reject_unverified_citations_and_count_omissions(self) -> None:
        fixture = {
            "contract": {
                "clauses": [
                    {"id": "EPC-01", "text": "Delay creates liquidated damages."},
                    {"id": "EPC-02", "text": "Price is fixed."},
                ]
            },
            "n4_oracle": {
                "expected_risks": [
                    {
                        "clause_id": "EPC-01",
                        "risk": "Delay LD exposure",
                        "category": "SCHEDULE",
                        "citation_must_include": "liquidated damages",
                    },
                    {
                        "clause_id": "EPC-02",
                        "risk": "Fixed-price allocation",
                        "category": "BUDGET",
                        "citation_must_include": "Price is fixed",
                    },
                ]
            },
        }
        risks = [
            {
                "title": "Delay exposure",
                "description": "Liquidated damages apply.",
                "category": "SCHEDULE",
                "source_quote": "Delay creates liquidated damages.",
                "source_quote_status": "VERIFIED",
            },
            {
                "title": "Invented risk",
                "description": "Not present.",
                "category": "LEGAL",
                "source_quote": "Not in the contract.",
                "source_quote_status": "NOT_FOUND_IN_DOCUMENT",
            },
        ]

        result = runner.score_n4(fixture, risks)

        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["omissions"], 1)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["valid_citations"], 1)
        self.assertEqual(result["invalid_citations"], 1)

    def test_abbreviated_oracle_marker_matches_source_order_not_literal_dots(self) -> None:
        quote = (
            "Force Majeure. Price escalation, currency fluctuation, lack of financing "
            "and ordinary market shortages are not Force Majeure."
        )
        marker = "lack of financing ... are not Force Majeure"
        self.assertTrue(runner._source_marker_matches(marker, quote))
        self.assertTrue(runner._source_marker_matches(marker.replace("...", "…"), quote))
        self.assertFalse(runner._source_marker_matches(marker, "lack of financing permits delay relief."))
        self.assertFalse(
            runner._source_marker_matches(marker, "are not Force Majeure if there is lack of financing")
        )

    def test_n4_scoring_accepts_valid_epc05_quote_with_abbreviated_oracle(self) -> None:
        source = (
            "Price escalation, currency fluctuation, lack of financing and "
            "ordinary market shortages are not Force Majeure."
        )
        fixture = {
            "contract": {"clauses": [{"id": "EPC-05", "text": source}]},
            "n4_oracle": {"expected_risks": [{
                "clause_id": "EPC-05",
                "category": "LEGAL",
                "citation_must_include": "lack of financing ... are not Force Majeure",
            }]},
        }
        result = runner.score_n4(fixture, [{
            "title": "Financing excluded",
            "category": "LEGAL",
            "source_quote": source,
            "source_quote_status": "VERIFIED",
        }])
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["omissions"], 0)

    def test_n12_metrics_require_both_omissions_and_the_false_interpretation(self) -> None:
        notes = (
            "EPC-04 defect cure obligation is absent. EPC-07 liability-cap carve-outs are absent. "
            "EPC-05 is wrong because lack of financing and currency fluctuation are not Force Majeure."
        )

        result = runner.score_n12(notes)

        self.assertEqual(result["omissions_detected"], 2)
        self.assertTrue(result["incorrect_interpretation_detected"])


if __name__ == "__main__":
    unittest.main()
