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

    def test_n12_citation_gate_rejects_mixed_genuine_and_invented_quotes(self) -> None:
        source = (
            "EPC-04: The Contractor must rectify each notified defect within fourteen days. "
            "EPC-07: The Contractor liability cap excludes deliberate misconduct."
        )
        real_quote = "The Contractor must rectify each notified defect within fourteen days."
        invented_quote = "The parties agreed unlimited insurance coverage with no exclusions."
        notes = (
            "EPC-04 defect obligation: “" + real_quote + "” "
            "EPC-07 liability: “" + invented_quote + "”"
        )
        metric = runner.score_n12(notes, source)
        self.assertEqual(metric["critique_quoted_citations"], 2)
        self.assertEqual(metric["critique_valid_quoted_citations"], 1)
        self.assertEqual(metric["critique_invalid_quoted_citations"], 1)
        self.assertFalse(metric["critique_citation_validity"])

    @staticmethod
    def _three_source_findings() -> tuple[str, list[dict[str, str]]]:
        fixture = runner.load_fixture()
        source = runner._source_text(fixture)
        clauses = {clause["id"]: clause["text"] for clause in fixture["contract"]["clauses"]}
        findings = [
            {
                "clause_ref": ref,
                "issue_type": "contradiction" if ref == "EPC-05" else "omission",
                "source_quote": clauses[ref][:155],
                "explanation": "Check the source-backed obligation, interpretation awaits HITL.",
            }
            for ref in ("EPC-04", "EPC-05", "EPC-07")
        ]
        return source, findings

    def test_n12_raw_payload_all_three_provenances_verified_without_semantic_approval(self) -> None:
        source, findings = self._three_source_findings()
        actual = runner.score_n12_structured_provenance(
            {"findings": findings, "status": "RETRY"}, source
        )
        self.assertTrue(actual["model_findings_payload_valid"])
        self.assertEqual(actual["model_findings_submitted"], 3)
        self.assertEqual(actual["model_findings_source_verified"], 3)
        self.assertEqual(actual["model_findings_unverified"], 0)
        self.assertEqual(set(actual["model_verified_clause_refs"]), {"EPC-04", "EPC-05", "EPC-07"})

    def test_n12_raw_payload_cannot_hide_hallucination_after_notes_sanitization(self) -> None:
        source, findings = self._three_source_findings()
        hallucinated = {
            **findings[0],
            "clause_ref": "EPC-07",
            "source_quote": findings[0]["source_quote"],
            "explanation": "Invented EPC-07 provenance for an EPC-04 quote.",
        }
        stats = runner.score_n12_structured_provenance(
            {"findings": findings + [hallucinated]}, source
        )
        self.assertTrue(stats["model_findings_payload_valid"])
        self.assertEqual(stats["model_findings_submitted"], 4)
        self.assertEqual(stats["model_findings_source_verified"], 3)
        self.assertEqual(stats["model_findings_unverified"], 1)

    def test_n12_unstructured_model_response_never_passes_provenance_gate(self) -> None:
        source, _ = self._three_source_findings()
        stats = runner.score_n12_structured_provenance({"status": "OK"}, source)
        self.assertFalse(stats["model_findings_payload_valid"])
        self.assertEqual(stats["model_findings_source_verified"], 0)

    def test_n12_citation_gate_requires_source_quotes_not_bare_ids(self) -> None:
        source = (
            "EPC-04: The Contractor shall rectify defects after notice. "
            "EPC-07: The Contractor shall indemnify the Client."
        )
        self.assertFalse(
            runner.score_n12("EPC-04 and EPC-07 are omitted", source)["critique_citation_validity"]
        )
        good = (
            "EPC-04: “The Contractor shall rectify defects after notice.” "
            "EPC-07: “The Contractor shall indemnify the Client.”"
        )
        metric = runner.score_n12(good, source)
        self.assertTrue(metric["critique_citation_validity"])
        self.assertEqual(metric["critique_invalid_quoted_citations"], 0)


if __name__ == "__main__":
    unittest.main()
