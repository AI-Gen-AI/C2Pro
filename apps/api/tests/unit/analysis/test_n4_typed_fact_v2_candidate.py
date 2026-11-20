"""Tests for N4 v2 *proposed* EPC facts, not any live LLM result."""
from __future__ import annotations
import hashlib
import json
import unittest
from types import SimpleNamespace as NS

from src.analysis.domain.n4_typed_fact_v2_candidate import (
    N4TypedFactContractError, parse_n4_typed_fact_candidate_response,
)

WINDOW=NS(
    ordinal=4,
    revision_id="synthetic-revision-0001",
    source_sha256=hashlib.sha256(b"synthetic").hexdigest(),
    context_start=100,
    context_text=(
        "Clause 9.6: Contractor shall notify Owner within ten working days. "
        "The agreed milestone is 30 June 2027. Annex F is not attached."
    ),
)


def fact(entity_type="obligation", dimensions=None, quote=None, **extra):
    return {
        "entity_type":entity_type,
        "dimensions":dimensions if dimensions is not None else ["LEGAL","TIME"],
        "statement":"Contractor notification obligation",
        "source_quote":quote if quote is not None else
            "Contractor shall notify Owner within ten working days",
        "clause_ref":"9.6",
        **extra,
    }


def parse(facts, refs=None, examined=True, window=WINDOW):
    payload={
        "window_examined":examined, "facts":facts,
        "outstanding_references":refs if refs is not None else [],
    }
    return parse_n4_typed_fact_candidate_response(payload,window=window)


class TypedFactV2Tests(unittest.TestCase):
    def test_exact_quote_and_two_orthogonal_dimensions(self):
        result=parse([fact()])
        self.assertEqual(result.window_ordinal,4)
        item=result.candidate_facts[0]
        self.assertEqual(item["entity_type"],"obligation")
        self.assertEqual(item["dimensions"],("LEGAL","TIME"))
        self.assertEqual(item["evidence"]["evidence_status"],"EXACT_MODEL_SAFE_MATCH")
        self.assertEqual(item["verbatim_quote"],fact()["source_quote"])
        a,b=item["evidence"]["analysis_span"]
        self.assertEqual(a,WINDOW.context_start+WINDOW.context_text.find(item["verbatim_quote"]))
        self.assertEqual(b-a,len(item["verbatim_quote"]))
        self.assertEqual(item["evidence"]["original_pdf_page_attestation"],"UNVERIFIED")
        self.assertEqual(result.trusted_promotions,0)
        self.assertEqual(result.n12_status,"UNASSESSED")

    def test_fact_type_does_not_replace_dimension(self):
        result=parse([
            fact(entity_type="milestone", dimensions=["TIME"]),
            fact(entity_type="risk_hypothesis",dimensions=["LEGAL","BUDGET"],
                 hypothesis_reason="Candidate delay impact, not an observed obligation"),
        ])
        self.assertEqual(result.candidate_facts[0]["entity_type"],"milestone")
        self.assertEqual(result.candidate_facts[0]["dimensions"],("TIME",))
        self.assertEqual(result.candidate_facts[1]["entity_type"],"risk_hypothesis")
        self.assertEqual(result.candidate_facts[1]["interpretation"],"Candidate delay impact, not an observed obligation")

    def test_invalid_typed_dimension_and_type_fail(self):
        with self.assertRaisesRegex(N4TypedFactContractError,"dimensions"):
            parse([fact(dimensions=["COST"])])
        with self.assertRaisesRegex(N4TypedFactContractError,"entity_type"):
            parse([fact(entity_type="verified_contradiction")])
        with self.assertRaisesRegex(N4TypedFactContractError,"dimensions"):
            parse([fact(dimensions=["TIME","TIME"])])

    def test_unverifiable_quote_retains_candidate_without_literal(self):
        bad=fact(quote="The Contractor guarantees unconditional profit")
        result=parse([fact(),bad])
        self.assertEqual(len(result.candidate_facts),2)
        self.assertEqual(result.candidate_facts[1]["evidence"]["evidence_status"],
                         "NOT_FOUND_IN_MODEL_SAFE_SOURCE")
        self.assertIsNone(result.candidate_facts[1]["verbatim_quote"])
        self.assertIsNone(result.candidate_facts[1]["evidence"]["analysis_span"])
        self.assertEqual(result.candidate_facts[0]["evidence"]["evidence_status"],"EXACT_MODEL_SAFE_MATCH")

    def test_missing_quote_is_a_hypothesis_not_sourced(self):
        candidate=fact()
        candidate["source_quote"]=None
        result=parse([candidate])
        self.assertEqual(result.candidate_facts[0]["evidence"]["evidence_status"],"MISSING_SOURCE_QUOTE")

    def test_repeated_quote_is_ambiguous_not_approved(self):
        duplicated=NS(**{**vars(WINDOW),
          "context_text":"Owner shall approve. Owner shall approve."})
        result=parse([fact(quote="Owner shall approve")],window=duplicated)
        self.assertEqual(result.candidate_facts[0]["evidence"]["evidence_status"],"AMBIGUOUS_REPEATED_QUOTE")

    def test_missing_annex_keeps_facts_and_coverage_partial(self):
        result=parse([fact()],refs=["Annex F not supplied"])
        self.assertEqual(len(result.candidate_facts),1)
        self.assertEqual(result.outstanding_references,("Annex F not supplied",))
        self.assertEqual(result.source_coverage_state,"PARTIAL_OR_REFERENCES_PENDING")

    def test_invalid_envelope_or_risk_interpretation_fails(self):
        with self.assertRaisesRegex(N4TypedFactContractError,"truncated"):
            parse_n4_typed_fact_candidate_response('{"window_examined":',window=WINDOW)
        with self.assertRaisesRegex(N4TypedFactContractError,"interpretation"):
            parse([fact(entity_type="risk_hypothesis", dimensions=["TIME"])])
        with self.assertRaisesRegex(N4TypedFactContractError,"boolean"):
            parse_n4_typed_fact_candidate_response(
                {"window_examined":"yes","facts":[],"outstanding_references":[]},window=WINDOW
            )


if __name__=="__main__":
    unittest.main()
