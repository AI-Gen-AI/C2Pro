"""Disentangle source/citation/category problems without weakening N4 oracle."""

from scripts import n4_n12_real_ai_eval as runner


def _mini_fixture() -> dict:
    return {
        "contract": {
            "clauses": [
                {
                    "id": "EPC-01",
                    "text": "The Contractor pays LD for delay, capped at ten percent.",
                },
                {
                    "id": "EPC-02",
                    "text": "The Employer shall pay all invoices within forty five days.",
                },
                {
                    "id": "EPC-03",
                    "text": "The Contractor obtains written instructions for change orders.",
                },
            ]
        },
        "n4_oracle": {
            "expected_risks": [
                {
                    "clause_id": "EPC-01",
                    "category": "SCHEDULE",
                    "citation_must_include": "LD for delay",
                },
                {
                    "clause_id": "EPC-02",
                    "category": "BUDGET",
                    "citation_must_include": "all invoices within forty five days",
                },
                {
                    "clause_id": "EPC-03",
                    "category": "SCOPE",
                    "citation_must_include": "written instructions for change orders",
                },
            ]
        },
    }


def test_diagnostic_distinguishes_wrong_category_from_missing_marker_and_invalid_quote() -> None:
    fixture = _mini_fixture()
    risks = [
        {
            "category": "LEGAL",
            "source_quote": "The Contractor pays LD for delay, capped at ten percent.",
            "source_quote_status": "VERIFIED",
        },
        {
            "category": "BUDGET",
            "source_quote": "The Employer shall pay all invoices",
            "source_quote_status": "VERIFIED",
        },
        {
            "category": "SCOPE",
            "source_quote": None,
            "source_quote_status": "NOT_FOUND_IN_DOCUMENT",
        },
    ]
    result = runner.score_n4(fixture, risks)
    assert result["true_positives"] == 0
    assert result["false_positives"] == 3
    assert result["unmatched_emitted_risks"] == 3
    assert result["invalid_citations"] == 1
    by_clause = {item["clause_id"]: item for item in result["unmatched_diagnosis"]}
    assert by_clause["EPC-01"]["candidate_count_by_reason"]["valid_marker_different_category"] == 1
    assert (
        by_clause["EPC-02"]["candidate_count_by_reason"][
            "same_category_clause_quote_missing_marker"
        ]
        == 1
    )
    assert by_clause["EPC-03"]["candidate_count_by_reason"]["globally_unverified_quotes"] == 1
    assert all(x["diagnostic_only_no_semantic_acceptance"] for x in by_clause.values())


def test_proper_quote_still_passes_and_diagnostics_empty() -> None:
    fixture = _mini_fixture()
    risks = [
        {
            "category": e["category"],
            "source_quote": f"{c['id']}: {c['text']}",
            "source_quote_status": "VERIFIED",
        }
        for e, c in zip(
            fixture["n4_oracle"]["expected_risks"],
            fixture["contract"]["clauses"],
            strict=True,
        )
    ]
    result = runner.score_n4(fixture, risks)
    assert result["true_positives"] == 3
    assert result["invalid_citations"] == 0
    assert result["unmatched_diagnosis"] == []


def test_diagnosis_is_deterministic_and_does_not_store_raw_llm_text() -> None:
    fixture = runner.load_fixture()
    source = runner._source_text(fixture)
    risks = [
        {
            "category": item["category"],
            "source_quote": fixture["contract"]["clauses"][i]["text"],
            "source_quote_status": "VERIFIED",
        }
        for i, item in enumerate(fixture["n4_oracle"]["expected_risks"])
    ]
    metrics = runner.score_n4(fixture, risks)
    assert metrics["true_positives"] == 9
    assert not metrics["unmatched_diagnosis"]
    assert source[:80] not in str(metrics)
