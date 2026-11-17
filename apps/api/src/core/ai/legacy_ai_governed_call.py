"""Opt-in bridge: one pre-authorized legacy AI call with durable cost escrow.

Use only with a provider wrapper configured for no automatic retries/cache.
Neither provider exceptions nor malformed responses release the reservation.
A caller repeating an idempotency key is NOT allowed to call the model again.

This bridge is separate from N4's window ledger and does NOT approve source
risks or change the interpretation of any contractual document.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from src.core.ai.legacy_ai_reservation_store import (
    LegacyAIReservationError,
    reconcile_legacy_ai,
    reserve_legacy_ai,
)
from src.core.database import get_session_with_tenant


class LegacyAICostUnverified(LegacyAIReservationError):
    """Provider returned content without usable charge; output must not be trusted."""


async def execute_budgeted_legacy_call(
    *, tenant_id: UUID, idempotency_key: str, source: str,
    max_charge_usd: Decimal | str,
    invoke: Callable[[str], Awaitable[Any]],
) -> Any:
    """Reserve -> provider (no DB locks) -> settle once, else retain UNKNOWN.

    Note: `invoke` MUST perform at most one model request or a tightly
    capped provider-native sequence. This component deliberately never
    retries the callback. Caller controls JSON parse/quality.
    """
    async with get_session_with_tenant(tenant_id) as session:
        hold = await reserve_legacy_ai(
            session, tenant_id=tenant_id, idempotency_key=idempotency_key,
            source=source, max_charge_usd=max_charge_usd,
        )
    # The context manager committed before the first billable side effect.
    if hold.replay:
        raise LegacyAIReservationError(
            "existing AI reservation requires reconciliation, not a second model request"
        )

    try:
        response = await invoke(str(hold.reservation_id))
    except Exception as exc:
        observed = getattr(exc, "cost_usd", None)
        usage = {
            "input_tokens": getattr(exc, "input_tokens", None),
            "output_tokens": getattr(exc, "output_tokens", None),
            "provider_model": getattr(exc, "model", None),
        }
        try:
            known_price = (
                Decimal(str(observed))
                if observed is not None else None
            )
            if known_price is not None and (
                not known_price.is_finite() or known_price < 0
                or (
                    known_price == 0 and (
                        usage["input_tokens"] or usage["output_tokens"]
                    )
                )
            ):
                known_price = None
        except (ValueError, TypeError, InvalidOperation):
            known_price = None
        # Never cover up failed reconciliation with a fabricated zero charge.
        async with get_session_with_tenant(tenant_id) as session:
            await reconcile_legacy_ai(
                session, tenant_id=tenant_id,
                reservation_id=hold.reservation_id,
                billed_usd=known_price,
                **usage,
            )
        raise

    raw_cost = getattr(response, "cost_usd", None)
    try:
        actual = Decimal(str(raw_cost)) if raw_cost is not None else None
        if (
            actual is None or not actual.is_finite() or actual < 0
            or (
                actual == 0 and (
                    getattr(response, "input_tokens", 0)
                    or getattr(response, "output_tokens", 0)
                )
            )
        ):
            raise ValueError("unverified provider usage")
    except (InvalidOperation, ValueError, TypeError):
        async with get_session_with_tenant(tenant_id) as session:
            await reconcile_legacy_ai(
                session, tenant_id=tenant_id,
                reservation_id=hold.reservation_id, billed_usd=None,
                input_tokens=getattr(response, "input_tokens", None),
                output_tokens=getattr(response, "output_tokens", None),
                provider_model=getattr(response, "model_used", None),
            )
        raise LegacyAICostUnverified(
            "model result cost unavailable: unknown charge held; result not accepted"
        ) from None

    async with get_session_with_tenant(tenant_id) as session:
        await reconcile_legacy_ai(
            session, tenant_id=tenant_id,
            reservation_id=hold.reservation_id, billed_usd=actual,
            input_tokens=getattr(response, "input_tokens", None),
            output_tokens=getattr(response, "output_tokens", None),
            provider_model=getattr(response, "model_used", None),
        )
    return response
