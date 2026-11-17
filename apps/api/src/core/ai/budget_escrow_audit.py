"""Read-only financial integrity audit across V4 N4 and legacy AI ledgers.

This is not a settlement system. UNKNOWN calls must be reconciled with
provider evidence by an independently authorized procedure; no amount is
released, guessed, or written by this module.

A tenant row FOR SHARE lock pins all escrow mutations during the snapshot,
because both N4 and legacy reserve/reconcile acquire tenant FOR UPDATE
before changing their respective ledger rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TenantBudgetAuditError(RuntimeError):
    """Budget facts could not be safely inspected in tenant context."""


@dataclass(frozen=True, slots=True)
class PendingLedger:
    source: str
    reserved_usd: Decimal
    reserved_count: int
    unknown_count: int
    stale_reserved_count: int
    stale_unknown_count: int
    oldest_held_at: str | None
    settled_overage_count: int
    settled_overage_usd: Decimal


@dataclass(frozen=True, slots=True)
class TenantBudgetAudit:
    tenant_id: UUID
    recorded_escrow_usd: Decimal
    calculated_escrow_usd: Decimal
    n4_tenant_bucket_reserved_usd: Decimal
    n4: PendingLedger
    legacy: PendingLedger
    confirmed_spend_usd: Decimal
    monthly_cap_usd: Decimal
    findings: tuple[str, ...]

    @property
    def financial_reconciliation_passed(self) -> bool:
        return not any(
            code in self.findings
            for code in (
                "GLOBAL_ESCROW_MISMATCH",
                "N4_TENANT_BUCKET_MISMATCH",
                "INVALID_TENANT_BALANCE",
            )
        )

    @property
    def needs_provider_followup(self) -> bool:
        return (
            self.n4.unknown_count > 0 or self.legacy.unknown_count > 0
            or self.n4.stale_reserved_count > 0
            or self.legacy.stale_reserved_count > 0
            or self.n4.settled_overage_count > 0
            or self.legacy.settled_overage_count > 0
        )


def _decimal(value: object) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise TenantBudgetAuditError("financial snapshot contains invalid amount")
    return amount


async def _pending(
    session: AsyncSession, *, tenant: UUID, table: str,
    stale_after_hours: int,
) -> PendingLedger:
    if table not in ("n4_usage_reservations", "legacy_ai_usage_reservations"):
        raise ValueError("only the two audited usage ledgers are supported")
    # The actual hold is fixed and must remain funded even after an UNKNOWN
    # provider result. Settled rows have already transferred into spend.
    # Compare settled known usage to the original estimate independently
    # of tenant's monthly cap: a $0.48 charge vs $0.30 hold must be visible
    # even if the tenant still has credit available.
    actual_column = (
        "spent_usd" if table == "n4_usage_reservations" else "billed_usd"
    )
    row = (await session.execute(text(f"""
        SELECT
          COALESCE(sum(reserved_usd)
            FILTER (WHERE status IN ('RESERVED','UNKNOWN')), 0) AS held,
          count(*) FILTER (WHERE status='RESERVED') AS reserved_calls,
          count(*) FILTER (WHERE status='UNKNOWN') AS unknown_calls,
          count(*) FILTER (
              WHERE status='RESERVED'
                AND created_at < clock_timestamp()
                    - (:age * interval '1 hour')
          ) AS stale_reserved,
          count(*) FILTER (
              WHERE status='UNKNOWN'
                AND created_at < clock_timestamp()
                    - (:age * interval '1 hour')
          ) AS stale_unknown,
          min(created_at) FILTER (
              WHERE status IN ('RESERVED','UNKNOWN')
          ) AS oldest_held,
          count(*) FILTER (
              WHERE status='SETTLED'
                AND {actual_column} > reserved_usd
          ) AS overage_count,
          COALESCE(sum({actual_column} - reserved_usd) FILTER (
              WHERE status='SETTLED'
                AND {actual_column} > reserved_usd
          ), 0) AS overage_usd
        FROM public.{table}
        WHERE tenant_id = CAST(:tenant AS uuid)
    """), {"tenant": str(tenant), "age": stale_after_hours})).mappings().one()
    return PendingLedger(
        source="N4" if table.startswith("n4_") else "LEGACY",
        reserved_usd=_decimal(row["held"]),
        reserved_count=int(row["reserved_calls"]),
        unknown_count=int(row["unknown_calls"]),
        stale_reserved_count=int(row["stale_reserved"]),
        stale_unknown_count=int(row["stale_unknown"]),
        oldest_held_at=(
            row["oldest_held"].isoformat() if row["oldest_held"] else None
        ),
        settled_overage_count=int(row["overage_count"]),
        settled_overage_usd=_decimal(row["overage_usd"]),
    )


async def audit_tenant_escrow(
    session: AsyncSession, *, tenant_id: UUID, stale_after_hours: int = 24,
) -> TenantBudgetAudit:
    """Inspect two ledgers, financial counters and N4 TENANT bucket together.

    The caller owns the transaction (do not commit inside). It must set
    `app.current_tenant` to the authorized tenant. This routine never
    enumerates other tenants and never changes reservations or balances.

    Use the result before enabling new payment/provider paths. A clean
    snapshot alone does NOT validate actual provider invoices.
    """
    if type(stale_after_hours) is not int or not 1 <= stale_after_hours <= 720:
        raise ValueError("stale_after_hours must be an integer from 1 to 720")
    tenant = UUID(str(tenant_id))
    selected = await session.scalar(text(
        "SELECT current_setting('app.current_tenant', true)"
    ))
    if selected != str(tenant):
        raise TenantBudgetAuditError("tenant context not verified")
    row = (await session.execute(text("""
        SELECT ai_spend_reserved_usd, ai_spend_current, ai_budget_monthly
          FROM public.tenants
         WHERE id=CAST(:tenant AS uuid)
         FOR SHARE
    """), {"tenant": str(tenant)})).mappings().one_or_none()
    if row is None:
        raise TenantBudgetAuditError("tenant not found")
    n4 = await _pending(
        session, tenant=tenant, table="n4_usage_reservations",
        stale_after_hours=stale_after_hours,
    )
    legacy = await _pending(
        session, tenant=tenant, table="legacy_ai_usage_reservations",
        stale_after_hours=stale_after_hours,
    )
    bucket = (await session.execute(text("""
        SELECT COALESCE(sum(reserved_usd),0)
          FROM public.n4_budget_buckets
         WHERE tenant_id=CAST(:tenant AS uuid) AND scope_kind='TENANT'
    """), {"tenant": str(tenant)})).scalar_one()
    actual = _decimal(row["ai_spend_reserved_usd"])
    projected = n4.reserved_usd + legacy.reserved_usd
    n4_bucket = _decimal(bucket)
    spent = _decimal(row["ai_spend_current"])
    cap = _decimal(row["ai_budget_monthly"])
    findings: list[str] = []
    if actual != projected:
        findings.append("GLOBAL_ESCROW_MISMATCH")
    if n4_bucket != n4.reserved_usd:
        findings.append("N4_TENANT_BUCKET_MISMATCH")
    if min(actual, spent, cap) < 0:
        findings.append("INVALID_TENANT_BALANCE")
    if actual + spent > cap:
        # Overage may be an authentic provider charge, not corruption.
        findings.append("CAP_EXCEEDED_REQUIRES_REVIEW")
    if n4.settled_overage_count or legacy.settled_overage_count:
        findings.append("PROVIDER_CHARGE_EXCEEDED_RESERVATION")
    if n4.unknown_count or legacy.unknown_count:
        findings.append("UNRECONCILED_PROVIDER_USAGE")
    if n4.stale_reserved_count or legacy.stale_reserved_count:
        findings.append("STALE_INFLIGHT_RESERVATIONS")
    if n4.stale_unknown_count or legacy.stale_unknown_count:
        findings.append("STALE_UNKNOWN_PROVIDER_USAGE")
    return TenantBudgetAudit(
        tenant_id=tenant, recorded_escrow_usd=actual,
        calculated_escrow_usd=projected,
        n4_tenant_bucket_reserved_usd=n4_bucket,
        n4=n4, legacy=legacy,
        confirmed_spend_usd=spent, monthly_cap_usd=cap,
        findings=tuple(findings),
    )
