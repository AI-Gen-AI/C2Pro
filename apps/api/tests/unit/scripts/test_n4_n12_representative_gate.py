"""Independent acceptance must reject forged runner gates and SDK-ledger drift."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import n4_n12_real_ai_eval as oracle
from scripts import n4_n12_representative_eval as trial
from scripts import n4_n12_representative_gate as gate
from scripts.real_ai_governor.real_ai_governor import usd as governed_usd
from tests.unit.scripts.test_n4_n12_representative_eval import representative_success


def valid_evidence() -> tuple[dict, list[dict], dict]:
    fixture = oracle.load_fixture()
    report = deepcopy(representative_success())
    report.update(
        {
            "fixture_id": fixture["fixture_id"],
            "fixture_sha256": oracle.FIXTURE_SHA256,
            "profile": "normal_core_sonnet_8192",
            "model": gate.EXPECTED_MODEL,
            "ai_mock": False,
            "provider_call": "real",
            "production_uat": False,
            "human_review_required_by_use_case": True,
            "hitl_pause_in_graph_tested": False,
            "limits": {"max_calls": 3, "max_usd": 1.0},
            "gates": dict.fromkeys(
                (
                    "provider_bounded",
                    "n4_nine_source_risks",
                    "n4_source_prepared",
                    "n12_adversarial_grounded",
                    "n12_chained_no_invented_source",
                ),
                True,
            ),
        }
    )
    coverage = report["input_coverage"]
    coverage.update(
        {
            "source_clause_ids_retained": [x["id"] for x in fixture["contract"]["clauses"]],
            "n2_mode": "synthetic_projection_not_real_anonymizer",
            "prepared_sha256": "a" * 64,
            "prepared_characters": 2700,
        }
    )
    report["n4"].update(model=gate.EXPECTED_MODEL, input_tokens=1233, output_tokens=3500)
    clauses_by_id = {c["id"]: c["text"] for c in fixture["contract"]["clauses"]}
    report["n4"]["citation_fingerprints"] = trial.n4_citation_fingerprints(
        [
            {
                "category": item["category"],
                "source_quote_status": "VERIFIED",
                "source_quote": clauses_by_id[item["clause_id"]],
            }
            for item in fixture["n4_oracle"]["expected_risks"]
        ],
        oracle._source_text(fixture),
    )
    a = report["n12_adversarial"]
    a.update(
        evaluation="adversarial_fixture",
        model_declared_status="RETRY",
        quality_state="NOT_ASSESSED",
        parse_failure_type=None,
        response_sha256="b" * 64,
        notes_sha256="c" * 64,
    )
    c = report["n12_chained"]
    c.update(
        evaluation="actual_n4_output",
        quality_state="NOT_ASSESSED",
        n4_risks_submitted=9,
        model_declared_status="OK",
        model_neutral_ok_notes=True,
        response_sha256="d" * 64,
        notes_sha256="e" * 64,
    )
    ledger: list[dict] = []
    for i, (tokens_in, tokens_out) in enumerate(((1233, 3500), (2600, 650), (4100, 440))):
        ledger.extend(
            [
                {"ev": "reserve", "id": f"reservation-{i}", "model": gate.EXPECTED_MODEL},
                {
                    "ev": "done",
                    "id": f"reservation-{i}",
                    "model": gate.EXPECTED_MODEL,
                    "in": tokens_in,
                    "out": tokens_out,
                    "stop_reason": "end_turn",
                    "usd": round(governed_usd(gate.EXPECTED_MODEL, tokens_in, tokens_out), 6),
                },
            ]
        )
    provider = report["provider"]
    total_cost = round(sum(e["usd"] for e in ledger if e["ev"] == "done"), 6)
    provider.update(
        calls=3,
        completed_calls=3,
        refusals=0,
        failed_calls=0,
        models=[gate.EXPECTED_MODEL],
        input_tokens=7933,
        output_tokens=4590,
        estimated_cost_usd=total_cost,
    )
    return report, ledger, fixture


def test_gate_accepts_complete_raw_oracle_without_human_approval() -> None:
    report, ledger, fixture = valid_evidence()
    gate.verify_report(report, ledger, fixture)


@pytest.mark.parametrize(
    ("axis", "attack"),
    [
        ("runner_forged_gates", lambda r, e: r["n4"].update(true_positives=8)),
        ("ledger_missing_completion", lambda r, e: e.pop()),
        ("ledger_unknown_model", lambda r, e: e[1].update(model="claude-haiku-4-5-20251001")),
        ("ledger_output_truncated", lambda r, e: e[1].update(stop_reason="max_tokens")),
        (
            "ledger_extra_reservation",
            lambda r, e: e.append({"ev": "reserve", "id": "extra", "model": gate.EXPECTED_MODEL}),
        ),
        ("ledger_over_budget", lambda r, e: e[1].update(usd=1.1)),
        ("ledger_underpriced_from_tokens", lambda r, e: e[1].update({"in": 999999})),
        ("n4_case_category", lambda r, e: r["n4"]["cases"][0].update(expected_category="LEGAL")),
        (
            "n4_quote_hash_forged",
            lambda r, e: r["n4"]["citation_fingerprints"][0].update(
                normalized_quote_sha256="f" * 64
            ),
        ),
        (
            "n4_quote_start_forged",
            lambda r, e: r["n4"]["citation_fingerprints"][0].update(normalized_start=10),
        ),
        (
            "n4_quote_category_forged",
            lambda r, e: r["n4"]["citation_fingerprints"][0].update(category="LEGAL"),
        ),
        (
            "n4_quote_status_forged",
            lambda r, e: r["n4"]["citation_fingerprints"][0].update(
                source_quote_status="UNVERIFIED"
            ),
        ),
        ("n4_quote_proof_missing", lambda r, e: r["n4"].pop("citation_fingerprints")),
        ("n12_bad_source", lambda r, e: r["n12_adversarial"].update(model_findings_unverified=1)),
        (
            "n12_chained_unstructured",
            lambda r, e: r["n12_chained"].update(model_findings_payload_valid=False),
        ),
        (
            "n12_chained_invalid_quote",
            lambda r, e: r["n12_chained"].update(critique_invalid_quoted_citations=1),
        ),
        (
            "n12_human_gate_lost",
            lambda r, e: r["n12_chained"].update(human_approval_required=False),
        ),
        (
            "chained_empty_retry",
            lambda r, e: r["n12_chained"].update(model_declared_status="RETRY"),
        ),
        (
            "chained_empty_unverified_ok",
            lambda r, e: r["n12_chained"].update(model_neutral_ok_notes=False),
        ),
        ("graph_hitl_falsely_claimed", lambda r, e: r.update(hitl_pause_in_graph_tested=True)),
    ],
)
def test_independent_gate_fails_closed_even_if_runner_says_true(axis, attack) -> None:
    report, ledger, fixture = valid_evidence()
    attack(report, ledger)
    assert all(report["gates"].values()), axis
    with pytest.raises((AssertionError, KeyError, TypeError)):
        gate.verify_report(report, ledger, fixture)


def test_independent_n4_rescoring_preserves_mismatch_diagnostics() -> None:
    """A real-looking 4/9 result stays FAIL, never auto-credited as nine risks."""
    fixture = oracle.load_fixture()
    source = oracle._source_text(fixture)
    clauses = {entry["id"]: entry["text"] for entry in fixture["contract"]["clauses"]}
    risks = []
    for i, expected in enumerate(fixture["n4_oracle"]["expected_risks"]):
        # Four valid + one source quote found with wrong category; the rest
        # are withheld as NOT_FOUND/NOT_PROVIDED exactly as the CORE does.
        if i < 4:
            category = expected["category"]
            quote, status = clauses[expected["clause_id"]], "VERIFIED"
        elif i == 4:
            category = "BUDGET" if expected["category"] != "BUDGET" else "LEGAL"
            quote, status = clauses[expected["clause_id"]], "VERIFIED"
        else:
            category = expected["category"]
            quote, status = None, "NOT_PROVIDED" if i == 5 else "NOT_FOUND_IN_DOCUMENT"
        risks.append(
            {
                "category": category,
                "source_quote": quote,
                "source_quote_status": status,
            }
        )
    fingerprints = trial.n4_citation_fingerprints(risks, source)
    rescored = gate.independently_rescore_n4(fixture, fingerprints)
    existing = oracle.score_n4(fixture, risks)
    for key in (
        "emitted_risks",
        "true_positives",
        "false_positives",
        "valid_citations",
        "invalid_citations",
        "omissions",
        "cases",
    ):
        assert rescored[key] == existing[key], key
    assert rescored["emitted_risks"] == 9
    assert rescored["true_positives"] == 4
    assert rescored["valid_citations"] == 5
    assert rescored["invalid_citations"] == 4
    assert rescored["false_positives"] == 5
