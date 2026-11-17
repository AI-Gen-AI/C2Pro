"""Offline, credential-free financial check of a V4.1 real pilot artifact.

Never promotes a financial ledger assertion into a verified provider invoice.
This module does not access providers, databases, model outputs or document
text. It reads only receipt/status summary fields from the evidence JSON
produced by v41_contract_real_ai_pilot.py. The pilot's isolated tenant must
contain exclusively the run being audited to compare its balance to receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

_ZERO = Decimal("0")
_LIMIT = Decimal("1000000000")


@dataclass(frozen=True, slots=True)
class V41FinanceEvidenceResult:
    status: str
    internal_ledger_consistent: bool
    invoice_verified: bool
    confirmed_spend_usd: Decimal
    pending_hold_usd: Decimal
    reported_tenant_spend_usd: Decimal | None
    reported_tenant_hold_usd: Decimal | None
    n4_receipt_count: int
    legacy_receipt_count: int
    findings: tuple[str, ...]

    def sanitized_summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "internal_ledger_consistent": self.internal_ledger_consistent,
            "invoice_verified": False,
            "confirmed_spend_usd": str(self.confirmed_spend_usd),
            "pending_hold_usd": str(self.pending_hold_usd),
            "reported_tenant_spend_usd": (
                str(self.reported_tenant_spend_usd)
                if self.reported_tenant_spend_usd is not None else None
            ),
            "reported_tenant_hold_usd": (
                str(self.reported_tenant_hold_usd)
                if self.reported_tenant_hold_usd is not None else None
            ),
            "n4_receipt_count": self.n4_receipt_count,
            "legacy_receipt_count": self.legacy_receipt_count,
            "findings": list(self.findings),
            "note": "Internal ledger check only; provider invoice NOT verified",
        }


def _d(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount < _ZERO or amount > _LIMIT:
        return None
    return amount


def audit_v41_financial_evidence(report: object) -> V41FinanceEvidenceResult:
    """Check financial equality without trusting any semantic model result."""
    issues: list[str] = []
    if not isinstance(report, dict):
        report = {}
        issues.append("REPORT_NOT_OBJECT")
    n4 = report.get("n4")
    if not isinstance(n4, dict):
        n4 = {}
    n4_rows = n4.get("receipts")
    if not isinstance(n4_rows, list):
        n4_rows = report.get("last_n4_receipts")
    legacy_rows = report.get("shared_ledger")
    if not isinstance(legacy_rows, list):
        legacy_rows = report.get("last_legacy_receipts")
    balance = report.get("tenant_balance")
    if not isinstance(balance, dict):
        balance = {}
        issues.append("TENANT_BALANCE_MISSING")
    if not isinstance(n4_rows, list) or not isinstance(legacy_rows, list):
        issues.append("LEDGER_SNAPSHOT_MISSING")
        n4_rows = n4_rows if isinstance(n4_rows, list) else []
        legacy_rows = legacy_rows if isinstance(legacy_rows, list) else []

    spend = _ZERO
    holds = _ZERO
    keys: set[tuple[str, object]] = set()
    provider_requests: dict[str, str] = {}
    for lane, rows, spent_field, key_field in (
        ("N4", n4_rows, "spent_usd", "window_ordinal"),
        ("LEGACY", legacy_rows, "billed_usd", "idempotency_key"),
    ):
        for item in rows:
            if not isinstance(item, dict):
                issues.append(lane + "_ROW_INVALID")
                continue
            key = item.get(key_field)
            if key is None or (lane == "LEGACY" and not str(key).strip()):
                issues.append(lane + "_KEY_MISSING")
                continue
            if (lane, str(key)) in keys:
                issues.append(lane + "_DUPLICATE_RECEIPT_KEY")
                continue
            keys.add((lane, str(key)))
            provider_id = item.get("provider_request_id")
            if isinstance(provider_id, str) and provider_id.strip():
                previous_lane = provider_requests.get(provider_id)
                if previous_lane is not None:
                    issues.append(
                        "CROSS_LANE_PROVIDER_REQUEST_DUPLICATE"
                        if previous_lane != lane
                        else lane + "_PROVIDER_REQUEST_DUPLICATE"
                    )
                    continue
                provider_requests[provider_id] = lane
            status = item.get("status")
            reserved = _d(item.get("reserved_usd"))
            billed = _d(item.get(spent_field))
            if reserved is None or reserved <= _ZERO:
                issues.append(lane + "_INVALID_RESERVE")
                continue
            if status == "SETTLED":
                if billed is None:
                    issues.append(lane + "_SETTLED_WITHOUT_BILL")
                else:
                    spend += billed
                    if billed > reserved:
                        issues.append(lane + "_KNOWN_OVERAGE_REVIEW")
                    tokens_in = item.get("input_tokens")
                    tokens_out = item.get("output_tokens")
                    if tokens_in is None or tokens_out is None:
                        issues.append(lane + "_TOKEN_RECEIPT_INCOMPLETE")
                    elif (
                        type(tokens_in) is not int or tokens_in < 0
                        or type(tokens_out) is not int or tokens_out < 0
                    ):
                        issues.append(lane + "_TOKEN_RECEIPT_INVALID")
                    elif billed == _ZERO and tokens_in + tokens_out > 0:
                        issues.append(lane + "_ZERO_COST_WITH_TOKENS")
            elif status in ("RESERVED", "UNKNOWN"):
                if billed is not None:
                    issues.append(lane + "_PENDING_HAS_BILL")
                holds += reserved
                if status == "UNKNOWN":
                    issues.append(lane + "_UNKNOWN_PROVIDER_USAGE")
                else:
                    issues.append(lane + "_INFLIGHT_RESERVATION")
            elif status == "CANCELED" and lane == "N4":
                if billed is not None:
                    issues.append(lane + "_CANCELED_HAS_BILL")
            else:
                issues.append(lane + "_INVALID_STATUS")

    spend_reported = _d(balance.get("ai_spend_current"))
    reserved_reported = _d(balance.get("ai_spend_reserved_usd"))
    cap_reported = _d(balance.get("ai_budget_monthly"))
    if spend_reported is None or reserved_reported is None or cap_reported is None:
        issues.append("TENANT_COUNTERS_INVALID")
    else:
        if spend_reported != spend:
            issues.append("TENANT_CONFIRMED_SPEND_MISMATCH")
        if reserved_reported != holds:
            issues.append("TENANT_RESERVED_SPEND_MISMATCH")
        if spend_reported + reserved_reported > cap_reported:
            issues.append("GLOBAL_MONTHLY_CAP_EXCEEDED")
    src = report.get("source")
    if (
        isinstance(src, dict)
        and n4.get("total_windows") is not None
        and src.get("n4_windows_planned") != n4.get("total_windows")
    ):
        issues.append("SOURCE_WINDOW_INVENTORY_MISMATCH")
    if n4.get("status") != "COMPLETE":
        issues.append("N4_ANALYSIS_NOT_COMPLETE")
    elif (
        n4.get("examined_windows") != n4.get("total_windows")
        or type(n4.get("total_windows")) is not int
        or n4.get("total_windows") <= 0
    ):
        issues.append("WINDOW_COVERAGE_INCOMPLETE")
    if (
        n4.get("status") == "COMPLETE"
        and type(n4.get("total_windows")) is int
        and len(n4_rows) != n4["total_windows"]
    ):
        issues.append("N4_RECEIPT_COVERAGE_INCOMPLETE")

    consistency_faults = {
        code for code in issues if code.endswith((
            "_MISMATCH", "_INVALID", "_WITHOUT_BILL",
            "_KEY_MISSING", "_DUPLICATE_RECEIPT_KEY", "_MISSING",
            "_HAS_BILL", "_WITH_TOKENS", "_INCOMPLETE",
            "_DUPLICATE",
        )) or code in ("REPORT_NOT_OBJECT", "TENANT_BALANCE_MISSING")
    }
    consistent = not consistency_faults
    if "LEDGER_SNAPSHOT_MISSING" in issues:
        status = "NOT_AUDITABLE"
        consistent = False
    elif not consistent:
        status = "INTERNAL_LEDGER_INCONSISTENT"
    elif "N4_ANALYSIS_NOT_COMPLETE" in issues:
        status = "PARTIAL_PILOT_NO_GO"
    elif any("UNKNOWN_PROVIDER_USAGE" in code for code in issues):
        status = "PENDING_PROVIDER_RECONCILIATION"
    elif "GLOBAL_MONTHLY_CAP_EXCEEDED" in issues or any(
        code.endswith("_KNOWN_OVERAGE_REVIEW") for code in issues
    ):
        status = "KNOWN_OVERAGE_REQUIRES_REVIEW"
    elif any("INFLIGHT_RESERVATION" in code for code in issues):
        status = "PENDING_INFLIGHT_RESERVATIONS"
    else:
        status = "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED"
    return V41FinanceEvidenceResult(
        status=status,
        internal_ledger_consistent=consistent,
        invoice_verified=False,
        confirmed_spend_usd=spend,
        pending_hold_usd=holds,
        reported_tenant_spend_usd=spend_reported,
        reported_tenant_hold_usd=reserved_reported,
        n4_receipt_count=len(n4_rows),
        legacy_receipt_count=len(legacy_rows),
        findings=tuple(sorted(set(issues))),
    )
