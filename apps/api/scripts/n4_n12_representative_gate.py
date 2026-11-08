"""Independent metrics + provider-ledger acceptance gate.

This code does NOT trust the runner's precomputed gates. It reads the immutable
fixture, checks source/quality metrics and independently reconciles the SDK
governor ledger. No model calls, secrets, prompts or completions.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from scripts import n4_n12_real_ai_eval as fixture_contract
from scripts.real_ai_governor.real_ai_governor import usd as governed_usd

REPORT_PATH = (
    fixture_contract.API_ROOT.parent / "web/playwright-report/n4-n12-representative-evaluation.json"
)
EXPECTED_MODEL = "claude-sonnet-4-6"


def verify_report(
    report: dict[str, Any],
    ledger_events: list[dict[str, Any]],
    fixture: dict[str, Any],
) -> None:
    """Raise AssertionError on any mismatch; ignore precomputed runner gates."""
    assert report["fixture_sha256"] == fixture_contract.FIXTURE_SHA256
    assert report["fixture_id"] == fixture["fixture_id"]
    assert report["profile"] == "normal_core_sonnet_8192"
    assert report["model"] == EXPECTED_MODEL
    assert report["ai_mock"] is False and report["provider_call"] == "real"
    assert report["production_uat"] is False
    assert report["hitl_pause_in_graph_tested"] is False
    assert report["human_review_required_by_use_case"] is True

    coverage = report["input_coverage"]
    ids = [str(item["id"]) for item in fixture["contract"]["clauses"]]
    assert len(ids) == 9
    assert coverage["fixture_clauses"] == 9
    assert coverage["source_clauses_retained"] == 9
    assert coverage["source_clause_ids_retained"] == ids
    assert coverage["n2_mode"] == "synthetic_projection_not_real_anonymizer"
    assert len(coverage["prepared_sha256"]) == 64
    assert coverage["prepared_characters"] > 0

    reserves = [e for e in ledger_events if e.get("ev") == "reserve"]
    dones = [e for e in ledger_events if e.get("ev") == "done"]
    assert len(reserves) == 3 and len(dones) == 3
    assert not [e for e in ledger_events if e.get("ev") in {"fail", "refused"}]
    reserve_ids = [e["id"] for e in reserves]
    done_ids = [e["id"] for e in dones]
    assert len(set(reserve_ids)) == 3 and set(done_ids) == set(reserve_ids)
    assert all(e["model"] == EXPECTED_MODEL for e in reserves)
    assert all(e["model"] == EXPECTED_MODEL for e in dones)
    assert all(e.get("stop_reason") == "end_turn" for e in dones)
    assert all(0 < int(e["out"]) <= 8192 and int(e["in"]) > 0 for e in dones)
    independently_priced = [
        round(governed_usd(EXPECTED_MODEL, int(e["in"]), int(e["out"])), 6) for e in dones
    ]
    for actual, expected in zip(dones, independently_priced, strict=True):
        assert math.isclose(float(actual["usd"]), expected, abs_tol=0.000001)
    total = sum(independently_priced)
    assert math.isfinite(total) and 0 < total <= 1.0
    assert report["limits"] == {"max_calls": 3, "max_usd": 1.0}
    provider = report["provider"]
    assert provider["calls"] == 3 and provider["completed_calls"] == 3
    assert provider["failed_calls"] == 0 and provider["refusals"] == 0
    assert provider["models"] == [EXPECTED_MODEL]
    assert provider["input_tokens"] == sum(int(e["in"]) for e in dones)
    assert provider["output_tokens"] == sum(int(e["out"]) for e in dones)
    assert math.isclose(provider["estimated_cost_usd"], total, abs_tol=0.000003)

    n4 = report["n4"]
    oracle_items = fixture["n4_oracle"]["expected_risks"]
    assert len(oracle_items) == 9
    assert n4["model"] == EXPECTED_MODEL
    assert n4["expected_risks"] == n4["true_positives"] == 9
    assert n4["emitted_risks"] == 9
    assert n4["omissions"] == n4["false_positives"] == n4["invalid_citations"] == 0
    assert n4["valid_citations"] == 9
    cases = n4["cases"]
    assert len(cases) == 9
    assert [case["clause_id"] for case in cases] == [item["clause_id"] for item in oracle_items]
    for case, expected in zip(cases, oracle_items, strict=True):
        assert case["expected_category"] == expected["category"]
        assert case["extracted"] is True and case["citation_valid"] is True
    assert n4["input_tokens"] == int(dones[0]["in"])
    assert n4["output_tokens"] == int(dones[0]["out"])

    a = report["n12_adversarial"]
    assert a["evaluation"] == "adversarial_fixture"
    assert a["omissions_expected"] == a["omissions_detected"] == 2
    assert a["omission_cases"] == {"EPC-04": True, "EPC-07": True}
    assert a["incorrect_interpretation_expected"] == 1
    assert a["incorrect_interpretation_detected"] is True
    refs = {"EPC-04", "EPC-05", "EPC-07"}
    assert refs.issubset(set(a["critique_citation_clause_refs"]))
    assert refs.issubset(set(a["model_verified_clause_refs"]))
    assert a["critique_citation_validity"] is True
    assert a["critique_quoted_citations"] >= 3
    assert a["critique_valid_quoted_citations"] == a["critique_quoted_citations"]
    assert a["critique_invalid_quoted_citations"] == 0
    assert a["model_declared_status"] == "RETRY"
    assert a["model_findings_payload_valid"] is True
    assert a["model_findings_submitted"] >= 3
    assert a["model_findings_source_verified"] == a["model_findings_submitted"]
    assert a["model_findings_unverified"] == 0

    c = report["n12_chained"]
    assert c["evaluation"] == "actual_n4_output"
    assert c["n4_risks_submitted"] == n4["emitted_risks"]
    assert c["model_findings_payload_valid"] is True
    assert c["model_findings_source_verified"] == c["model_findings_submitted"]
    assert c["model_findings_unverified"] == 0
    # Zero findings are meaningful only for an explicit, neutral model OK.
    # Requiring a fabricated criticism when N4 covered all clauses would
    # make the evaluator reward false positives; RETRY requires findings.
    if c["model_findings_submitted"] == 0:
        assert c["model_declared_status"] == "OK"
        assert c["model_neutral_ok_notes"] is True
    else:
        assert c["model_declared_status"] == "RETRY"
    assert c["critique_invalid_quoted_citations"] == 0
    for item in (a, c):
        assert item["status"] == "UNASSESSED"
        assert item["quality_state"] == "NOT_ASSESSED"
        assert item["human_approval_required"] is True
        assert item["semantic_approval"] is False
        assert item["parse_failure_type"] is None
        assert len(item["response_sha256"]) == 64
        assert len(item["notes_sha256"]) == 64

    # No trust in report["gates"]: a forged all-True dict does not bypass raw checks.


def main() -> int:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    ledger = os.environ.get("C2PRO_AI_GOVERNOR_LEDGER")
    if not ledger:
        raise RuntimeError("C2PRO_AI_GOVERNOR_LEDGER_MISSING")
    events = [
        json.loads(line)
        for line in Path(ledger).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    fixture = fixture_contract.load_fixture()
    verify_report(report, events, fixture)
    print("INDEPENDENT_RAW_METRICS_AND_LEDGER_PASS")
    print("HITL_LEGAL_REVIEW_REQUIRED; PRODUCTION_UAT_NOT_ACREDITED")
    print(
        json.dumps(
            {
                "sha256": hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest(),
                "model": report["model"],
                "n4_true_positives": report["n4"]["true_positives"],
                "provider_calls": len([e for e in events if e["ev"] == "done"]),
                "estimated_usd": report["provider"]["estimated_cost_usd"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
