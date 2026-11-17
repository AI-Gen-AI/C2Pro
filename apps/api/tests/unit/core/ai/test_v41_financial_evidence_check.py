"""Financial summary parsing never certifies external invoices."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from src.core.ai.v41_financial_evidence_check import audit_v41_financial_evidence


def _evidence():
    return {
        "validation": "N3_N4_N12_LIVE_FINANCIAL_NOT_UAT",
        "source": {"n4_windows_planned": 2},
        "n4": {
            "status": "COMPLETE", "examined_windows": 2,
            "total_windows": 2,
            "receipts": [
                {
                    "window_ordinal": 0, "status": "SETTLED",
                    "reserved_usd": "0.15", "spent_usd": "0.08",
                    "input_tokens": 150, "output_tokens": 45,
                },
                {
                    "window_ordinal": 1, "status": "SETTLED",
                    "reserved_usd": "0.15", "spent_usd": "0.09",
                    "input_tokens": 155, "output_tokens": 53,
                },
            ],
        },
        "shared_ledger": [
            {
                "call_source": "N3_CLASSIFICATION", "status": "SETTLED",
                "reserved_usd": "0.35", "billed_usd": "0.12",
                "input_tokens": 85, "output_tokens": 20,
                "idempotency_key": "n3c-run",
            },
            {
                "call_source": "N12_FULL_SOURCE", "status": "RESERVED",
                "reserved_usd": "0.35", "billed_usd": None,
                "input_tokens": None, "output_tokens": None,
                "idempotency_key": "n12c-run",
            },
        ],
        "tenant_balance": {
            "ai_budget_monthly": 5,
            "ai_spend_current": "0.29",
            "ai_spend_reserved_usd": "0.35",
        },
        # A model answer may include secrets; never print or echo its text.
        "n8_projectgraph": {"document_text": "SECRET NOT TO EMIT"},
    }


def test_balanced_evidence_remains_not_an_invoice():
    summary = audit_v41_financial_evidence(_evidence())
    assert summary.internal_ledger_consistent
    assert not summary.invoice_verified
    assert summary.status == "PENDING_INFLIGHT_RESERVATIONS"
    assert "LEGACY_INFLIGHT_RESERVATION" in summary.findings
    assert summary.confirmed_spend_usd == Decimal('0.29')
    assert summary.pending_hold_usd == Decimal('0.35')
    assert "SECRET" not in str(summary.sanitized_summary())


def test_all_settled_balanced_report_still_not_invoice_verified():
    e = _evidence()
    e["shared_ledger"][1].update({
        "status": "SETTLED", "billed_usd": "0.05",
        "input_tokens": 45, "output_tokens": 10,
    })
    e["tenant_balance"]["ai_spend_current"] = "0.34"
    e["tenant_balance"]["ai_spend_reserved_usd"] = "0"
    result = audit_v41_financial_evidence(e)
    assert result.status == "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED"
    assert result.invoice_verified is False


def test_unknown_keeps_original_hold_and_is_not_free():
    e = _evidence()
    e["shared_ledger"][1]["status"] = "UNKNOWN"
    result = audit_v41_financial_evidence(e)
    assert result.internal_ledger_consistent
    assert result.pending_hold_usd == Decimal('0.35')
    assert result.status == "PENDING_PROVIDER_RECONCILIATION"
    assert "LEGACY_UNKNOWN_PROVIDER_USAGE" in result.findings


@pytest.mark.parametrize("mutation,signal", [
    ("missing_ledger", "LEDGER_SNAPSHOT_MISSING"),
    ("bad_spent_balance", "TENANT_CONFIRMED_SPEND_MISMATCH"),
    ("bad_hold_balance", "TENANT_RESERVED_SPEND_MISMATCH"),
    ("duplicate_n4", "N4_DUPLICATE_RECEIPT_KEY"),
    ("bad_settled_receipt", "N4_SETTLED_WITHOUT_BILL"),
    ("invalid_negative", "LEGACY_INVALID_RESERVE"),
    ("missing_tokens", "N4_TOKEN_RECEIPT_INCOMPLETE"),
    ("partial_windows", "WINDOW_COVERAGE_INCOMPLETE"),
])
def test_malformed_financial_evidence_is_detected(mutation, signal):
    e = deepcopy(_evidence())
    if mutation == "missing_ledger":
        e.pop("shared_ledger")
    elif mutation == "bad_spent_balance":
        e["tenant_balance"]["ai_spend_current"] = "0"
    elif mutation == "bad_hold_balance":
        e["tenant_balance"]["ai_spend_reserved_usd"] = "0"
    elif mutation == "duplicate_n4":
        e["n4"]["receipts"][1]["window_ordinal"] = 0
    elif mutation == "bad_settled_receipt":
        e["n4"]["receipts"][1]["spent_usd"] = None
    elif mutation == "invalid_negative":
        e["shared_ledger"][1]["reserved_usd"] = "-0.35"
    elif mutation == "missing_tokens":
        e["n4"]["receipts"][0]["input_tokens"] = None
    elif mutation == "partial_windows":
        e["n4"]["examined_windows"] = 1
    result = audit_v41_financial_evidence(e)
    assert signal in result.findings
    assert result.status != "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED"


def test_duplicate_receipts_are_excluded_from_reported_amounts():
    e = _evidence()
    e["n4"]["receipts"][1]["window_ordinal"] = 0
    result = audit_v41_financial_evidence(e)
    assert "N4_DUPLICATE_RECEIPT_KEY" in result.findings
    assert result.status == "INTERNAL_LEDGER_INCONSISTENT"
    assert result.confirmed_spend_usd == Decimal("0.20")
    assert "TENANT_CONFIRMED_SPEND_MISMATCH" in result.findings


def test_cross_lane_duplicate_provider_id_requires_comparable_identifiers():
    e = _evidence()
    e["n4"]["receipts"][0]["provider_request_id"] = "provider-call-1"
    e["shared_ledger"][0]["provider_request_id"] = "provider-call-1"
    result = audit_v41_financial_evidence(e)
    assert "CROSS_LANE_PROVIDER_REQUEST_DUPLICATE" in result.findings
    assert result.status == "INTERNAL_LEDGER_INCONSISTENT"
    assert result.confirmed_spend_usd == Decimal("0.17")
    assert "provider-call-1" not in str(result.sanitized_summary())


def test_known_overage_is_not_unknown():
    e = _evidence()
    e["shared_ledger"][1].update({
        "status": "SETTLED", "billed_usd": "0.48",
        "input_tokens": 290, "output_tokens": 55,
    })
    e["tenant_balance"]["ai_spend_current"] = "0.77"
    e["tenant_balance"]["ai_spend_reserved_usd"] = "0"
    result = audit_v41_financial_evidence(e)
    assert result.internal_ledger_consistent
    assert result.status == "KNOWN_OVERAGE_REQUIRES_REVIEW"
    assert result.confirmed_spend_usd == Decimal('0.77')
    assert result.pending_hold_usd == 0
    assert "LEGACY_KNOWN_OVERAGE_REVIEW" in result.findings


def test_cap_overrun_preserves_true_charge():
    e = _evidence()
    e["tenant_balance"]["ai_budget_monthly"] = "0.50"
    result = audit_v41_financial_evidence(e)
    assert result.status == "KNOWN_OVERAGE_REQUIRES_REVIEW"
    assert "GLOBAL_MONTHLY_CAP_EXCEEDED" in result.findings


def test_balanced_partial_pilot_is_not_misreported_as_complete():
    e = _evidence()
    e["n4"]["status"] = "PARTIAL"
    result = audit_v41_financial_evidence(e)
    assert result.internal_ledger_consistent
    assert result.status == "PARTIAL_PILOT_NO_GO"
    assert "N4_ANALYSIS_NOT_COMPLETE" in result.findings


def test_n4_complete_requires_one_receipt_per_window():
    e = _evidence()
    e["n4"]["receipts"].pop()
    e["tenant_balance"]["ai_spend_current"] = "0.20"
    result = audit_v41_financial_evidence(e)
    assert result.status == "INTERNAL_LEDGER_INCONSISTENT"
    assert "N4_RECEIPT_COVERAGE_INCOMPLETE" in result.findings


def test_missing_partial_report_is_not_a_free_run():
    result = audit_v41_financial_evidence({
        "validation": "NO_GO_PARTIAL_REAL_AI",
        "n3": {"status": "NOT_STARTED"},
    })
    assert result.status == "NOT_AUDITABLE"
    assert not result.invoice_verified
    assert result.confirmed_spend_usd == 0
    assert result.reported_tenant_spend_usd is None
