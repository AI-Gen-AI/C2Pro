"""Single direct OpenAI N4 provider, using committed N4 ledger escrow.

No Anthropic-first call, no OpenRouter, no retry and no ungoverned provider
call. The graph bridge selects this only when explicitly enabled in UAT.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from uuid import UUID

import httpx

from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_SYSTEM_PROMPT,
    n4_window_source_message,
)
from src.analysis.domain.n4_source_windows import N4SourceWindow
from src.core.ai.direct_provider_fallback import (
    DirectRoute,
    FallbackUnavailable,
    ProviderUsageUnknown,
    _estimate_max_charge,
    _invoke,
)
from src.core.ai.llm_client import LLMRequest


class DirectOpenAIN4WindowProvider:
    provider_name = "openai"
    fallback_routes = ()
    approved_fallback_models: frozenset[str] = frozenset()
    fallback_reservation_usd = None

    def __init__(self, *, max_output_tokens: int, reservation_usd: Decimal) -> None:
        raw = os.environ.get("C2PRO_N4_DIRECT_OPENAI_ROUTE")
        if not raw:
            raise FallbackUnavailable("Explicit UAT OpenAI direct route and rates missing")
        try:
            route = DirectRoute.from_dict(json.loads(raw))
        except (ValueError, TypeError, KeyError) as exc:
            raise FallbackUnavailable("Direct OpenAI route invalid") from exc
        if route.provider != "openai":
            raise FallbackUnavailable("Direct N4 primary must be OpenAI")
        if not (256 <= max_output_tokens <= 4096):
            raise FallbackUnavailable("N4 bounded output required")
        if max_output_tokens > route.output_tokens:
            raise FallbackUnavailable("N4 output exceeds verified model capacity")
        if not reservation_usd.is_finite() or reservation_usd <= 0:
            raise FallbackUnavailable("Positive per-window escrow required")
        self.route = route
        self.model_name = route.model
        self.max_output_tokens = max_output_tokens
        self.reservation_usd = reservation_usd

    async def generate(
        self, *, window: N4SourceWindow, tenant_id: UUID, request_id: str,
    ) -> N4ProviderReceipt:
        # The runner committed the reservation UUID before calling here.
        UUID(request_id)
        if not window.revision_id:
            raise FallbackUnavailable("N4 revision required")
        key = os.getenv("OPENAI_API_KEY")
        if not key or len(key) < 20:
            raise FallbackUnavailable("Direct OpenAI credential unavailable")
        request = LLMRequest(
            model=self.model_name,
            messages=[{"role": "user", "content": n4_window_source_message(window)}],
            system=N4_WINDOW_SYSTEM_PROMPT,
            max_tokens=self.max_output_tokens,
            temperature=0.0,
            request_id=request_id,
            tenant_id=tenant_id,
            metadata={"n4_incremental_window": True, "prompt_version": "n4-compact-window-v1"},
        )
        if _estimate_max_charge(self.route, request) > self.reservation_usd:
            raise FallbackUnavailable("Worst-case cost exceeds committed per-window escrow")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(90, connect=15), follow_redirects=False,
        ) as client:
            receipt = await _invoke(self.route, request, key=key, client=client)
        if Decimal(str(receipt.cost_usd)) > self.reservation_usd:
            raise ProviderUsageUnknown("Actual provider cost exceeds window escrow")
        return N4ProviderReceipt(
            content=receipt.content,
            model_used=receipt.model,
            reported_cost_usd=str(receipt.cost_usd),
            input_tokens=receipt.input_tokens,
            output_tokens=receipt.output_tokens,
            provider_request_id=receipt.request_id,
        )
