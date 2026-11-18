"""#1274 phase 2 transaction design. NEVER mounted/called by any runtime endpoint.

This service is intentionally NOT imported by the HTTP router. Runtime PATCH
always rejects (503) before it can acquire a DB session, even if an operator
configures a DSN. A separate CORE+SECURITY gate must review a distinct
least-privilege write capability, audit schema, full concurrency tests and
explicitly connect the runtime endpoint to this service.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class BudgetLimitEditInput(BaseModel):
    tenant_id: UUID
    period_key: str = Field(pattern=r"^20\d\d-(0[1-9]|1[0-2])$")
    expected_cap_usd: Decimal = Field(ge=0, max_digits=16, decimal_places=6)
    new_cap_usd: Decimal = Field(gt=0, max_digits=16, decimal_places=6)
    reason: str = Field(min_length=10, max_length=500)
    request_id: UUID
    confirmed: Literal[True]


class BudgetLimitConflict(Exception):
    """Stale state, inconsistent ledger, duplicate request or invalid cap."""


class BudgetLimitWriteResult(BaseModel):
    tenant_id: UUID
    period_key: str
    previous_cap_usd: Decimal
    new_cap_usd: Decimal
    request_id: UUID


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BudgetLimitConflict("Invalid accounting values") from exc
    if not result.is_finite() or result < 0:
        raise BudgetLimitConflict("Invalid accounting values")
    return result


def validate_budget_limit(
    *,
    old_tenant_cap: object,
    old_bucket_cap: object,
    tenant_spent: object,
    bucket_spent: object,
    tenant_reserved: object,
    bucket_reserved: object,
    request: BudgetLimitEditInput,
    owner_max_usd: Decimal,
) -> Decimal:
    """Conservative ledger check; UNKNOWN liability must be in reserved."""
    owner_cap = _money(old_tenant_cap)
    bucket_cap = _money(old_bucket_cap)
    old_expected = _money(request.expected_cap_usd)
    new_cap = _money(request.new_cap_usd)
    maximum = _money(owner_max_usd)
    if not request.reason.strip() or len(request.reason.strip()) < 10:
        raise BudgetLimitConflict("Reason must be meaningful")
    if owner_cap != bucket_cap or owner_cap != old_expected:
        raise BudgetLimitConflict("Stale or divergent TENANT cap")
    s1, s2 = _money(tenant_spent), _money(bucket_spent)
    r1, r2 = _money(tenant_reserved), _money(bucket_reserved)
    # Unknown provider obligations must already be in these reserved counters.
    if s1 != s2 or r1 != r2:
        raise BudgetLimitConflict("Ledger counters not reconciled")
    if new_cap < s1 + r1:
        raise BudgetLimitConflict("New cap below spend plus held reservations")
    if new_cap > maximum:
        raise BudgetLimitConflict("Exceeds independently approved owner maximum")
    return new_cap


async def apply_budget_limit_in_disposable_review(
    session: AsyncSession,
    *,
    request: BudgetLimitEditInput,
    owner_max_usd: Decimal,
    actor_clerk_id: str,
) -> BudgetLimitWriteResult:
    """Transaction reference ONLY; not wired to the API or persistent database.

    Exact row-lock order: TENANT row first, then current period TENANT bucket,
    matching reserve_call's tenant-first locking discipline. Audit INSERT
    failure rolls back both cap UPDATEs. The future DB principal must have
    column-exact UPDATE(cap_usd / ai_budget_monthly) + audited INSERT only,
    and no broad membership; security has NOT approved this grant model.
    """
    if not actor_clerk_id.startswith("user_"):
        raise BudgetLimitConflict("Operator identity must be a verified Clerk ID")
    if request.period_key != datetime.now(UTC).strftime("%Y-%m"):
        raise BudgetLimitConflict("Only current UTC period is editable")
    params = {"tenant": str(request.tenant_id), "period": request.period_key}
    async with session.begin():
        prior = (await session.execute(text("""
            SELECT tenant_id, period_key, before_cap_usd, after_cap_usd,
                   actor_clerk_id FROM public.platform_budget_limit_audit
             WHERE request_id=CAST(:request_id AS uuid)
        """), {"request_id": str(request.request_id)})).mappings().one_or_none()
        if prior is not None:
            if (str(prior["tenant_id"]) != str(request.tenant_id)
                or prior["period_key"] != request.period_key
                or _money(prior["after_cap_usd"]) != _money(request.new_cap_usd)
                or prior["actor_clerk_id"] != actor_clerk_id):
                raise BudgetLimitConflict("Request id collision")
            return BudgetLimitWriteResult(
                tenant_id=request.tenant_id, period_key=request.period_key,
                previous_cap_usd=_money(prior["before_cap_usd"]),
                new_cap_usd=_money(prior["after_cap_usd"]), request_id=request.request_id,
            )
        tenant = (await session.execute(text("""
            SELECT ai_budget_monthly AS cap,
                   ai_spend_current AS spent,
                   ai_spend_reserved_usd AS reserved
              FROM public.tenants
             WHERE id=CAST(:tenant AS uuid) AND is_active IS TRUE
             FOR UPDATE
        """), params)).mappings().one_or_none()
        bucket = (await session.execute(text("""
            SELECT cap_usd AS cap, spent_usd AS spent, reserved_usd AS reserved
              FROM public.n4_budget_buckets
             WHERE tenant_id=CAST(:tenant AS uuid) AND scope_kind='TENANT'
               AND scope_id=CAST(:tenant AS uuid) AND period_key=:period
             FOR UPDATE
        """), params)).mappings().one_or_none()
        if tenant is None or bucket is None:
            raise BudgetLimitConflict("Tenant or current TENANT bucket missing")
        new_cap = validate_budget_limit(
            old_tenant_cap=tenant["cap"], old_bucket_cap=bucket["cap"],
            tenant_spent=tenant["spent"], bucket_spent=bucket["spent"],
            tenant_reserved=tenant["reserved"], bucket_reserved=bucket["reserved"],
            request=request, owner_max_usd=owner_max_usd,
        )
        await session.execute(text("""
            UPDATE public.tenants SET ai_budget_monthly=:new_cap
             WHERE id=CAST(:tenant AS uuid)
        """), {**params, "new_cap": new_cap})
        await session.execute(text("""
            UPDATE public.n4_budget_buckets SET cap_usd=:new_cap
             WHERE tenant_id=CAST(:tenant AS uuid) AND scope_kind='TENANT'
               AND scope_id=CAST(:tenant AS uuid) AND period_key=:period
        """), {**params, "new_cap": new_cap})
        # Append-only durable audit is in the SAME transaction as both caps.
        await session.execute(text("""
            INSERT INTO public.platform_budget_limit_audit
                (request_id,tenant_id,period_key,actor_clerk_id,
                 before_cap_usd,after_cap_usd,reason,created_at)
            VALUES(CAST(:request_id AS uuid), CAST(:tenant AS uuid), :period, :actor,
                   :before, :new_cap, :reason, CURRENT_TIMESTAMP)
        """), {
            **params, "request_id": str(request.request_id),
            "actor": actor_clerk_id, "before": _money(tenant["cap"]),
            "new_cap": new_cap, "reason": request.reason.strip(),
        })
    return BudgetLimitWriteResult(
        tenant_id=request.tenant_id, period_key=request.period_key,
        previous_cap_usd=_money(tenant["cap"]), new_cap_usd=new_cap,
        request_id=request.request_id,
    )
