"""Adversarial offline evidence reconciliation, without provider invocations."""
from __future__ import annotations

from copy import deepcopy

import pytest

from src.core.ai.v41_governor_evidence_check import audit_v41_governor_evidence


def _data():
    report = {
        "source": {"n4_windows_planned": 1},
        "n4": {
            "total_windows": 1,
            "examined_windows": 1,
            "status": "COMPLETE",
            "receipts": [{
                "window_ordinal": 0, "status": "SETTLED",
                "reserved_usd": "0.20", "spent_usd": "0.09",
                "input_tokens": 100, "output_tokens": 20,
                "provider_request_id": "resp-n4-1",
                "model_name": "gpt-test",
            }],
        },
        "shared_ledger": [{
            "idempotency_key": "n3-test-001",
            "call_source": "N3_CLASSIFICATION",
            "status": "SETTLED", "reserved_usd": "0.10",
            "billed_usd": "0.04", "input_tokens": 45,
            "output_tokens": 10, "provider_model": "gpt-test",
        }],
        "tenant_balance": {
            "ai_spend_current": "0.13", "ai_spend_reserved_usd": "0",
            "ai_budget_monthly": "1",
        },
    }
    events = [
        {"ev": "reserve", "id": "call-n4", "estimated_max_usd": "0.20",
         "model": "gpt-test"},
        {"ev": "done", "id": "call-n4", "status": "completed",
         "request_id": "resp-n4-1", "cost_estimated_usd": "0.09",
         "input_tokens": 100, "output_tokens": 20, "model": "gpt-test"},
        {"ev": "reserve", "id": "call-n3", "estimated_max_usd": "0.10",
         "model": "gpt-test"},
        {"ev": "done", "id": "call-n3", "status": "completed",
         "request_id": "resp-n3-1", "cost_estimated_usd": "0.04",
         "input_tokens": 45, "output_tokens": 10, "model": "gpt-test"},
    ]
    return report, events


def test_governor_links_receipts_but_never_claims_provider_invoice():
    result = audit_v41_governor_evidence(*_data())
    assert result.status == "MATCHED_WITH_LIMITATIONS_NOT_INVOICE_VERIFIED"
    assert result.completed_calls == result.reserved_calls == 2
    assert result.n4_matched == 1
    assert result.governor_estimated_spend == result.ledger_estimated_spend
    assert not result.issues
    assert "LEGACY_PROVIDER_REQUEST_ID_UNBOUND" in result.limitations
    output = result.sanitized_summary()
    assert output["invoice_verified"] is False
    assert "resp-n4-1" not in str(output)


def test_partial_n4_never_becomes_a_successful_gate():
    report, events = _data()
    report["n4"].update(status="PARTIAL", examined_windows=0)
    result = audit_v41_governor_evidence(report, events)
    assert result.status == "GOVERNOR_LINKED_PARTIAL_PILOT_NO_GO"
    assert "FUNCTIONAL_OR_BUDGET_GATE_NOT_COMPLETE" in result.limitations


@pytest.mark.parametrize("mutation,signal", [
    ("provider_id_changed", "N4_GOVERNOR_RECEIPT_NOT_FOUND"),
    ("n4_tokens_changed", "N4_GOVERNOR_USAGE_MISMATCH"),
    ("n4_cost_changed", "N4_GOVERNOR_USAGE_MISMATCH"),
    ("n3_cost_changed", "LEGACY_GOVERNOR_USAGE_MISMATCH"),
    ("duplicate_done", "DUPLICATE_GOVERNOR_OPERATION"),
    ("duplicate_request", "DUPLICATE_GOVERNOR_PROVIDER_REQUEST"),
    ("missing_reserve", "GOVERNOR_RESERVE_COMPLETION_MISMATCH"),
    ("extra_done", "GOVERNOR_RESERVE_COMPLETION_MISMATCH"),
    ("n4_request_missing", "N4_PROVIDER_REQUEST_MISSING"),
    ("invalid_tokens", "INVALID_GOVERNOR_USAGE"),
    ("bill_changed", "BASE_LEDGER_NOT_CONSISTENT"),
])
def test_mutated_evidence_never_receives_clean_verdict(mutation, signal):
    report, events = deepcopy(_data())
    if mutation == "provider_id_changed":
        report["n4"]["receipts"][0]["provider_request_id"] = "not-in-log"
    elif mutation == "n4_tokens_changed":
        events[1]["output_tokens"] += 1
    elif mutation == "n4_cost_changed":
        events[1]["cost_estimated_usd"] = "0.090010"
    elif mutation == "n3_cost_changed":
        events[3]["cost_estimated_usd"] = "0.040010"
    elif mutation == "duplicate_done":
        events.append(deepcopy(events[1]))
    elif mutation == "duplicate_request":
        events[3]["request_id"] = events[1]["request_id"]
    elif mutation == "missing_reserve":
        events.pop(0)
    elif mutation == "extra_done":
        events.append(dict(events[3], id="extra-id", request_id="extra-response"))
    elif mutation == "n4_request_missing":
        report["n4"]["receipts"][0]["provider_request_id"] = ""
    elif mutation == "invalid_tokens":
        events[1]["input_tokens"] = -2
    elif mutation == "bill_changed":
        report["n4"]["receipts"][0]["spent_usd"] = "0.08"
    outcome = audit_v41_governor_evidence(report, events)
    assert outcome.status == "GOVERNOR_EVIDENCE_INCONSISTENT"
    assert signal in outcome.issues


def test_model_alias_is_not_misreported_as_provider_invoice():
    report, events = _data()
    events[1]["model"] = "gpt-test-2026-11-17"
    result = audit_v41_governor_evidence(report, events)
    assert result.status == "MATCHED_WITH_LIMITATIONS_NOT_INVOICE_VERIFIED"
    assert "MODEL_ALIAS_NOT_INVOICE_VERIFIED" in result.limitations
    assert not result.issues


def test_malformed_or_missing_event_list_is_not_auditable():
    report, _ = _data()
    for value in (None, [], {"fake": "event"}):
        assert audit_v41_governor_evidence(report, value).status == "NOT_AUDITABLE"
