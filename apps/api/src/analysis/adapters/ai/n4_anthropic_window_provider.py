"""Opt-in Anthropic transport for the source-safe N4 window runner.

Transport is isolated from graph orchestration. Instantiate only in an
authorized analysis-worker scope with a configured API key. No CLI OAuth
fallback, no implicit provider switching and NO automatic retry of billable
partial results. Returned price is *calculated from usage and routing rates*,
not a reconciled external provider invoice.
"""
from __future__ import annotations

import os
from decimal import Decimal
from uuid import UUID

from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_SYSTEM_PROMPT,
    n4_window_source_message,
)
from src.analysis.domain.n4_source_windows import N4SourceWindow
from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
from src.core.ai.direct_provider_fallback import approved_routes
from src.core.ai.model_router import AITaskType, ModelTier


class AnthropicN4WindowProvider:
    """Request bounded JSON, with NO full-source continuation or retry."""

    def __init__(
        self, *, wrapper: AnthropicWrapper,
        tier: ModelTier = ModelTier.STANDARD,
        max_output_tokens: int = 2048,
        fallback_reservation_usd: Decimal | str | None = None,
    ) -> None:
        if max_output_tokens < 256 or max_output_tokens > 4096:
            raise ValueError("N4 window output cap outside safe range")
        if wrapper.llm_client.max_retries != 0:
            raise ValueError("N4 provider must disable retry of billable calls")
        if wrapper.enable_cache or wrapper.cache_service is not None:
            raise ValueError("N4 provider must disable prompt cache for provenance")
        self.wrapper = wrapper
        self.tier = tier
        self.max_output_tokens = max_output_tokens
        self.model_name = wrapper.model_router.configs[tier].name
        self.fallback_reservation_usd = (
            Decimal(str(fallback_reservation_usd))
            if fallback_reservation_usd is not None else None
        )
        if self.fallback_reservation_usd is not None and (
            not self.fallback_reservation_usd.is_finite()
            or self.fallback_reservation_usd <= 0
        ):
            raise ValueError("N4 direct fallback requires positive finite reservation")
        self.fallback_routes = (
            approved_routes(os.getenv("C2PRO_DIRECT_FALLBACK_ROUTES"))
            if self.fallback_reservation_usd is not None else ()
        )
        if self.fallback_reservation_usd is not None and not self.fallback_routes:
            raise ValueError("N4 direct fallback requires explicit approved routes")
        self.approved_fallback_models = frozenset(
            route.model for route in self.fallback_routes
        )

    @classmethod
    def from_configured_account(
        cls, *, tier: ModelTier = ModelTier.STANDARD,
        max_output_tokens: int = 2048,
    ) -> AnthropicN4WindowProvider:
        return cls(
            wrapper=AnthropicWrapper(
                enable_cache=False,
                enable_retry=False,
                max_tokens_limit=max_output_tokens,
                timeout_seconds=75,
            ),
            tier=tier,
            max_output_tokens=max_output_tokens,
        )

    async def generate(
        self, *, window: N4SourceWindow, tenant_id: UUID, request_id: str,
    ) -> N4ProviderReceipt:
        if window.revision_id is None:
            raise ValueError("N4 source revision must be pinned")
        # Bypass re-anonymization ONLY because N4IncrementalRunner explicitly
        # requires an already N2-safe text projection. A second redaction pass
        # would otherwise invalidate source offsets and literal provenance.
        response = await self.wrapper.generate(AIRequest(
            prompt=n4_window_source_message(window),
            system_prompt=N4_WINDOW_SYSTEM_PROMPT,
            task_type=AITaskType.CONTRACT_EXTRACTION,
            force_model_tier=self.tier,
            max_tokens=self.max_output_tokens,
            temperature=0.0,
            tenant_id=tenant_id,
            request_id=request_id,
            low_budget_mode=False,
            use_cache=False,
            bypass_anonymization=True,
            metadata={
                "n4_incremental_window": True,
                "prompt_version": "n4-compact-window-v1",
                **(
                    {
                        "n4_reservation_committed": True,
                        "n4_reserved_usd": str(self.fallback_reservation_usd),
                    }
                    if self.fallback_reservation_usd is not None else {}
                ),
            },
        ))
        if response.model_used != self.model_name:
            # Runner will record the calculated cost and stop before
            # candidate acceptance; never mask rerouting to an unexpected model.
            return N4ProviderReceipt(
                content=response.content,
                model_used=response.model_used,
                reported_cost_usd=str(response.cost_usd),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                provider_request_id=getattr(response, "request_id", None) or request_id,
            )
        return N4ProviderReceipt(
            content=response.content,
            model_used=self.model_name,
            reported_cost_usd=str(Decimal(str(response.cost_usd))),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_request_id=getattr(response, "request_id", None) or request_id,
        )
