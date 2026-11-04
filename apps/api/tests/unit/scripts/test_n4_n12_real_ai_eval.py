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
