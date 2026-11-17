"""Fail-closed offline cross-check of a V4.1 governor JSONL and finance artifact.

The governor records estimated usage, NOT provider invoices. No network, DB,
LLM calls or document text are needed. Summaries never emit sensitive call IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from src.core.ai.v41_financial_evidence_check import audit_v41_financial_evidence

_MICRO = Decimal("0.000001")
_ZERO = Decimal("0")


def _money(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or result < _ZERO or result > Decimal("1000000000"):
        return None
    # Journal entries use six decimal places, while JSON floats may contain
    # harmless binary representation noise in the lower decimal digits.
    return result.quantize(_MICRO)


def _tokens(row: dict[str, Any]) -> tuple[int, int] | None:
    a, b = row.get("input_tokens"), row.get("output_tokens")
    if type(a) is not int or type(b) is not int or a < 0 or b < 0:
        return None
    return (a, b)


@dataclass(frozen=True, slots=True)
class GovernorEvidenceResult:
    status: str
    issues: tuple[str, ...]
    limitations: tuple[str, ...]
    n4_matched: int
    completed_calls: int
    reserved_calls: int
    governor_estimated_spend: Decimal
    ledger_estimated_spend: Decimal

    def sanitized_summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": list(self.issues),
            "limitations": list(self.limitations),
            "n4_matched": self.n4_matched,
            "completed_calls": self.completed_calls,
            "reserved_calls": self.reserved_calls,
            "governor_estimated_spend_usd": str(self.governor_estimated_spend),
            "ledger_estimated_spend_usd": str(self.ledger_estimated_spend),
            "invoice_verified": False,
        }


def audit_v41_governor_evidence(report: object, events: object) -> GovernorEvidenceResult:
    issues: set[str] = set()
    limitations: set[str] = {"PROVIDER_INVOICE_NOT_VERIFIED"}
    if not isinstance(report, dict) or not isinstance(events, list) or not events:
        return GovernorEvidenceResult(
            "NOT_AUDITABLE", ("MISSING_REPORT_OR_GOVERNOR",),
            tuple(sorted(limitations)), 0, 0, 0, _ZERO, _ZERO,
        )

    finance = audit_v41_financial_evidence(report)
    n4 = report.get("n4")
    n4rows = n4.get("receipts") if isinstance(n4, dict) else None
    legacy = report.get("shared_ledger")
    if not isinstance(n4rows, list) or not isinstance(legacy, list):
        issues.add("MISSING_LEDGER_RECEIPTS")
        n4rows = n4rows if isinstance(n4rows, list) else []
        legacy = legacy if isinstance(legacy, list) else []
    if not finance.internal_ledger_consistent:
        issues.add("BASE_LEDGER_NOT_CONSISTENT")
    if finance.status != "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED":
        limitations.add("FUNCTIONAL_OR_BUDGET_GATE_NOT_COMPLETE")

    reserves: dict[str, dict[str, Any]] = {}
    completions: dict[str, dict[str, Any]] = {}
    by_request: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict) or event.get("ev") not in ("reserve", "done"):
            issues.add("INVALID_GOVERNOR_EVENT")
            continue
        operation = event.get("id")
        if not isinstance(operation, str) or not operation.strip():
            issues.add("INVALID_GOVERNOR_CALL_ID")
            continue
        lane = reserves if event["ev"] == "reserve" else completions
        if operation in lane:
            issues.add("DUPLICATE_GOVERNOR_OPERATION")
            continue
        lane[operation] = event
        if event["ev"] == "done":
            if event.get("status") != "completed":
                issues.add("GOVERNOR_CALL_NOT_COMPLETED")
            request = event.get("request_id")
            if not isinstance(request, str) or not request.strip():
                issues.add("MISSING_GOVERNOR_PROVIDER_REQUEST")
            elif request in by_request:
                issues.add("DUPLICATE_GOVERNOR_PROVIDER_REQUEST")
            else:
                by_request[request] = event
            if _money(event.get("cost_estimated_usd")) is None or _tokens(event) is None:
                issues.add("INVALID_GOVERNOR_USAGE")
        elif _money(event.get("estimated_max_usd")) is None:
            issues.add("INVALID_GOVERNOR_RESERVATION")

    if set(reserves) != set(completions):
        issues.add("GOVERNOR_RESERVE_COMPLETION_MISMATCH")

    for key in set(reserves) & set(completions):
        done_cost = _money(completions[key].get("cost_estimated_usd"))
        reserve_cost = _money(reserves[key].get("estimated_max_usd"))
        # The estimate does not prove a hard provider cap: flag overages.
        if done_cost is not None and reserve_cost is not None and done_cost > reserve_cost:
            issues.add("GOVERNOR_ESTIMATE_EXCEEDED")
        if reserves[key].get("model") != completions[key].get("model"):
            limitations.add("GOVERNOR_MODEL_LABEL_VARIANT")

    governor_spend = sum((
        _money(e.get("cost_estimated_usd")) or _ZERO
        for e in completions.values()
    ), _ZERO)

    n4_requests: set[str] = set()
    matched = 0
    for receipt in n4rows:
        if not isinstance(receipt, dict):
            issues.add("INVALID_N4_RECEIPT")
            continue
        request = receipt.get("provider_request_id")
        if not isinstance(request, str) or not request.strip():
            issues.add("N4_PROVIDER_REQUEST_MISSING")
            continue
        if request in n4_requests:
            issues.add("N4_DUPLICATE_PROVIDER_REQUEST")
            continue
        n4_requests.add(request)
        event = by_request.get(request)
        if event is None:
            issues.add("N4_GOVERNOR_RECEIPT_NOT_FOUND")
            continue
        if (
            _money(receipt.get("spent_usd")) != _money(event.get("cost_estimated_usd"))
            or _tokens(receipt) != _tokens(event)
        ):
            issues.add("N4_GOVERNOR_USAGE_MISMATCH")
        else:
            matched += 1
        if receipt.get("model_name") != event.get("model"):
            limitations.add("MODEL_ALIAS_NOT_INVOICE_VERIFIED")

    residual = [x for k, x in by_request.items() if k not in n4_requests]
    if len(residual) != len(legacy):
        issues.add("LEGACY_GOVERNOR_COUNT_MISMATCH")
    if legacy:
        # Legacy N3 schema has no provider_request_id. Match one remaining
        # record by usage only; do not assert verified provider identity.
        limitations.add("LEGACY_PROVIDER_REQUEST_ID_UNBOUND")
    if len(residual) == 1 and len(legacy) == 1 and isinstance(legacy[0], dict):
        original = legacy[0]
        event = residual[0]
        if (_money(original.get("billed_usd")) != _money(event.get("cost_estimated_usd"))
                or _tokens(original) != _tokens(event)):
            issues.add("LEGACY_GOVERNOR_USAGE_MISMATCH")
        if original.get("provider_model") != event.get("model"):
            limitations.add("MODEL_ALIAS_NOT_INVOICE_VERIFIED")
    elif legacy:
        issues.add("LEGACY_IDENTITY_UNRESOLVED")

    if governor_spend != finance.confirmed_spend_usd:
        issues.add("GOVERNOR_TOTAL_SPEND_MISMATCH")
    if len(completions) != len(n4rows) + len(legacy):
        issues.add("GOVERNOR_COMPLETION_COUNT_MISMATCH")

    status = (
        "GOVERNOR_EVIDENCE_INCONSISTENT" if issues else
        "GOVERNOR_LINKED_PARTIAL_PILOT_NO_GO"
        if finance.status != "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED" else
        "MATCHED_WITH_LIMITATIONS_NOT_INVOICE_VERIFIED"
    )
    return GovernorEvidenceResult(
        status, tuple(sorted(issues)), tuple(sorted(limitations)),
        matched, len(completions), len(reserves), governor_spend,
        finance.confirmed_spend_usd,
    )
