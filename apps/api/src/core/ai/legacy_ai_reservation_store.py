"""Transactional reservations for legacy AI calls (V4 shared budget bridge).

This module contains no provider calls, no implicit COMMIT, and no semantic
rules. All mutations happen under a tenant-row lock and are committed by the
caller BEFORE the provider request. Every successful provider receipt must
be reconciled in a NEW transaction. Unknown billing is held, never zeroed.

Do not use this with a provider client that silently retries or dispatches
multiple requests under one reservation without a conservative cost cap.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_UP, Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_MONEY_UNIT = Decimal("0.000001")


class LegacyAIReservationError(RuntimeError):
    """An operation cannot be treated as a new billable call."""


class LegacyAIBudgetExceeded(LegacyAIReservationError):
    """Shared tenant monthly cap cannot cover the reservation."""


@dataclass(frozen=True, slots=True)
class LegacyAIHold:
    reservation_id: UUID
    status: str
    replay: bool


def _money(value: Decimal | float | int | str, *, require_positive: bool) -> Decimal:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("charge must be finite and nonnegative")
        amount = amount.quantize(_MONEY_UNIT, rounding=ROUND_UP)
        if require_positive and amount <= 0:
            raise ValueError("positive reserve required")
        return amount
    except (InvalidOperation, ValueError) as exc:
        raise LegacyAIReservationError("invalid AI budget amount") from exc


def _id(value: UUID) -> str:
    return str(UUID(str(value)))


async def _lock_tenant(
    session: AsyncSession, tenant_id: UUID, *, for_settlement: bool,
) -> dict[str, Any]:
    current = await session.scalar(
        text("SELECT current_setting('app.current_tenant', true)")
    )
    if current != str(tenant_id):
        raise LegacyAIReservationError("tenant scope is not explicitly pinned")
    row = (await session.execute(text("""
        SELECT id, ai_budget_monthly, ai_spend_current, ai_spend_reserved_usd,
               ai_spend_last_reset, is_active
          FROM public.tenants
         WHERE id = CAST(:tenant AS uuid)
         FOR UPDATE
    """), {"tenant": _id(tenant_id)})).mappings().one_or_none()
    if row is None:
        raise LegacyAIReservationError("tenant not found")
    balance = dict(row)
    try:
        for col in ("ai_budget_monthly", "ai_spend_current", "ai_spend_reserved_usd"):
            value = Decimal(str(balance[col]))
            if not value.is_finite() or value < 0:
                raise LegacyAIReservationError("invalid tenant budget state")
    except InvalidOperation as exc:
        raise LegacyAIReservationError("invalid tenant budget") from exc
    if not for_settlement and (
        not balance["is_active"] or Decimal(str(balance["ai_budget_monthly"])) <= 0
    ):
        raise LegacyAIBudgetExceeded("tenant has no active global budget")
    if not for_settlement:
        now = await session.scalar(
            text("SELECT clock_timestamp() AT TIME ZONE 'UTC'")
        )
        reset = balance["ai_spend_last_reset"]
        if reset is None or (reset.year, reset.month) != (now.year, now.month):
            await session.execute(text("""
                UPDATE public.tenants
                   SET ai_spend_current = 0, ai_spend_last_reset = :at
                 WHERE id = CAST(:tenant AS uuid)
            """), {"tenant": _id(tenant_id), "at": now})
            balance["ai_spend_current"] = 0.0
    return balance


async def reserve_legacy_ai(
    session: AsyncSession, *, tenant_id: UUID,
    idempotency_key: str, source: str,
    max_charge_usd: Decimal | float | int | str,
) -> LegacyAIHold:
    """Persist one escrow. Caller must COMMIT before model network activity."""
    if not (8 <= len(idempotency_key) <= 128):
        raise LegacyAIReservationError("stable 8–128-character idempotency key required")
    if not (1 <= len(source) <= 80):
        raise LegacyAIReservationError("short non-sensitive source tag required")
    amount = _money(max_charge_usd, require_positive=True)
    tenant = await _lock_tenant(session, tenant_id, for_settlement=False)
    existing = (await session.execute(text("""
        SELECT reservation_id, status, reserved_usd, call_source
          FROM public.legacy_ai_usage_reservations
         WHERE tenant_id=CAST(:tenant AS uuid) AND idempotency_key=:key
         FOR UPDATE
    """), {"tenant": _id(tenant_id), "key": idempotency_key})).mappings().one_or_none()
    if existing is not None:
        if Decimal(existing["reserved_usd"]) != amount or existing["call_source"] != source:
            raise LegacyAIReservationError("idempotency identity cannot change source or budget")
        return LegacyAIHold(UUID(str(existing["reservation_id"])), str(existing["status"]), True)
    remaining = (
        Decimal(str(tenant["ai_budget_monthly"]))
        - Decimal(str(tenant["ai_spend_current"]))
        - Decimal(str(tenant["ai_spend_reserved_usd"]))
    )
    if remaining < amount:
        raise LegacyAIBudgetExceeded("tenant spend and pending holds exceed global cap")
    reservation_id = uuid4()
    await session.execute(text("""
        INSERT INTO public.legacy_ai_usage_reservations
            (reservation_id, tenant_id, idempotency_key,
             call_source, reserved_usd, status)
        VALUES (CAST(:reservation AS uuid), CAST(:tenant AS uuid),
                :key, :source, :amount, 'RESERVED')
    """), {
        "reservation": _id(reservation_id), "tenant": _id(tenant_id),
        "key": idempotency_key, "source": source, "amount": amount,
    })
    await session.execute(text("""
        UPDATE public.tenants
           SET ai_spend_reserved_usd = ai_spend_reserved_usd + :amount
         WHERE id = CAST(:tenant AS uuid)
    """), {"tenant": _id(tenant_id), "amount": amount})
    return LegacyAIHold(reservation_id, "RESERVED", False)


async def reconcile_legacy_ai(
    session: AsyncSession, *, tenant_id: UUID, reservation_id: UUID,
    billed_usd: Decimal | float | int | str | None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    provider_model: str | None = None,
) -> str:
    """Idempotently transfer reserved→spent or hold UNKNOWN without release."""
    if any(type(n) is not int or n < 0 for n in (
        n for n in (input_tokens, output_tokens) if n is not None
    )):
        raise LegacyAIReservationError("token counts must be nonnegative integers")
    if provider_model is not None and (
        not provider_model.strip() or len(provider_model) > 128
    ):
        raise LegacyAIReservationError("invalid provider model reference")
    cost = None if billed_usd is None else _money(billed_usd, require_positive=False)
    await _lock_tenant(session, tenant_id, for_settlement=True)
    receipt = (await session.execute(text("""
        SELECT reservation_id, reserved_usd, billed_usd, status,
               input_tokens, output_tokens, provider_model
          FROM public.legacy_ai_usage_reservations
         WHERE tenant_id=CAST(:tenant AS uuid)
           AND reservation_id=CAST(:reservation AS uuid)
         FOR UPDATE
    """), {
        "tenant": _id(tenant_id), "reservation": _id(reservation_id),
    })).mappings().one_or_none()
    if receipt is None:
        raise LegacyAIReservationError("reservation absent for tenant")
    status = str(receipt["status"])
    if status == "SETTLED":
        if cost is None or Decimal(receipt["billed_usd"]) != cost or any(
            candidate is not None and candidate != receipt[key]
            for key, candidate in (
                ("input_tokens", input_tokens),
                ("output_tokens", output_tokens),
                ("provider_model", provider_model),
            )
        ):
            raise LegacyAIReservationError("replayed billable receipt has different usage")
        return "SETTLED"
    for key, candidate in (
        ("input_tokens", input_tokens), ("output_tokens", output_tokens),
        ("provider_model", provider_model),
    ):
        previous = receipt[key]
        if previous is not None and candidate is not None and previous != candidate:
            raise LegacyAIReservationError("usage provenance cannot change")
    if cost is None:
        await session.execute(text("""
            UPDATE public.legacy_ai_usage_reservations
               SET status='UNKNOWN',
                   input_tokens=COALESCE(:input, input_tokens),
                   output_tokens=COALESCE(:output, output_tokens),
                   provider_model=COALESCE(:model, provider_model)
             WHERE tenant_id=CAST(:tenant AS uuid)
               AND reservation_id=CAST(:reservation AS uuid)
        """), {
            "tenant": _id(tenant_id), "reservation": _id(reservation_id),
            "input": input_tokens, "output": output_tokens, "model": provider_model,
        })
        return "UNKNOWN"
    updated = await session.scalar(text("""
        UPDATE public.tenants
           SET ai_spend_reserved_usd=ai_spend_reserved_usd - :reserved,
               ai_spend_current=ai_spend_current + CAST(:actual AS double precision)
         WHERE id=CAST(:tenant AS uuid)
           AND ai_spend_reserved_usd >= :reserved
         RETURNING id
    """), {
        "tenant": _id(tenant_id), "reserved": Decimal(receipt["reserved_usd"]),
        "actual": cost,
    })
    if updated is None:
        raise LegacyAIReservationError("global tenant escrow missing or already released")
    await session.execute(text("""
        UPDATE public.legacy_ai_usage_reservations
           SET billed_usd=:actual, status='SETTLED',
               input_tokens=COALESCE(:input, input_tokens),
               output_tokens=COALESCE(:output, output_tokens),
               provider_model=COALESCE(:model, provider_model),
               settled_at=clock_timestamp()
         WHERE tenant_id=CAST(:tenant AS uuid)
           AND reservation_id=CAST(:reservation AS uuid)
    """), {
        "tenant": _id(tenant_id), "reservation": _id(reservation_id),
        "actual": cost, "input": input_tokens, "output": output_tokens,
        "model": provider_model,
    })
    return "SETTLED"
