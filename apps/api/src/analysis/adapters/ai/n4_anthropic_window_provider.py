"""Opt-in Anthropic transport for the source-safe N4 window runner.

Transport is isolated from graph orchestration. Instantiate only in an
authorized analysis-worker scope with a configured API key. No CLI OAuth
fallback, no implicit provider switching and NO automatic retry of billable
partial results. Returned price is *calculated from usage and routing rates*,
not a reconciled external provider invoice.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from uuid import UUID

from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_PROMPT_VERSION,
    N4_WINDOW_SYSTEM_PROMPT,
    n4_window_source_message,
)
from src.analysis.domain.n4_clause_inventory import (
    build_n4_clause_inventory,
    render_n4_clause_inventory_messages,
)
from src.analysis.domain.n4_source_windows import N4SourceWindow
from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
from src.core.ai.direct_provider_fallback import approved_routes
from src.core.ai.model_router import AITaskType, ModelTier



_N4_TOOL = {
    "name": "record_window_findings",
    "description": "Record all candidates and every examined clause.",
    "input_schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "window_examined": {"type": "boolean"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "title", "category", "risk_reason", "source_quote",
                        "supporting_quotes", "severity_proposed",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "category": {"type": "string", "enum": [
                            "LEGAL", "TIME", "BUDGET", "TECHNICAL",
                            "SCOPE", "QUALITY",
                        ]},
                        "risk_reason": {"type": "string"},
                        "source_quote": {"type": "string", "maxLength": 1200},
                        "supporting_quotes": {"type": "array", "maxItems": 2,
                                              "items": {"type": "string"}},
                        "severity_proposed": {"type": "string",
                                              "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
                        "clause_ref": {"type": ["string", "null"]},
                        "impact": {"type": ["string", "null"]},
                    },
                },
            },
            "examined_clauses": {"type": "array", "items": {
                "type": "object",
                "required": ["clause_ref", "examined", "has_risk"],
                "properties": {
                    "clause_ref": {"type": "string"},
                    "examined": {"type": "boolean"},
                    "has_risk": {"type": "boolean"},
                },
            }},
            "outstanding_references": {"type": "array",
                                       "items": {"type": "string"}},
        },
        "required": [
            "window_examined", "findings",
            "examined_clauses", "outstanding_references",
        ],
    },
}


def _v2_provider_response(raw: str) -> str:
    """Pin parser contract without fabricating examination or source evidence."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if not isinstance(payload, dict):
        return raw
    payload["prompt_version"] = N4_WINDOW_PROMPT_VERSION
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class AnthropicN4WindowProvider:
    """Request bounded JSON, with NO full-source continuation or retry."""
    provider_name = "anthropic"
    prompt_version = N4_WINDOW_PROMPT_VERSION

    def __init__(
        self, *, wrapper: AnthropicWrapper,
        tier: ModelTier = ModelTier.STANDARD,
        max_output_tokens: int = 8192,
        fallback_reservation_usd: Decimal | str | None = None,
    ) -> None:
        if max_output_tokens < 256 or max_output_tokens > 16384:
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
        max_output_tokens: int = 8192,
    ) -> AnthropicN4WindowProvider:
        return cls(
            wrapper=AnthropicWrapper(
                enable_cache=False,
                enable_retry=False,
                max_tokens_limit=16384,
                timeout_seconds=300,
            ),
            tier=tier,
            max_output_tokens=max_output_tokens,
        )

    async def generate(
        self, *, window: N4SourceWindow, tenant_id: UUID, request_id: str,
        attempt: int = 1,  # noqa: ARG002 - frozen by JV1-A1, used from A5
    ) -> N4ProviderReceipt:
        if attempt < 1:
            raise ValueError("N4 attempt must be positive and 1-based")
        output_cap = self.max_output_tokens if attempt == 1 else 16384
        inventory = build_n4_clause_inventory(window.context_text)
        inventory_context = "\n\n".join(
            render_n4_clause_inventory_messages(inventory)
        )
        if window.revision_id is None:
            raise ValueError("N4 source revision must be pinned")
        # Bypass re-anonymization ONLY because N4IncrementalRunner explicitly
        # requires an already N2-safe text projection. A second redaction pass
        # would otherwise invalidate source offsets and literal provenance.
        response = await self.wrapper.generate(AIRequest(
            prompt=n4_window_source_message(window) + "\n\n" + inventory_context,
            system_prompt=N4_WINDOW_SYSTEM_PROMPT,
            task_type=AITaskType.CONTRACT_EXTRACTION,
            force_model_tier=self.tier,
            max_tokens=output_cap,
            tools=[_N4_TOOL],
            tool_choice={"type": "tool", "name": "record_window_findings"},
            temperature=0.0,
            tenant_id=tenant_id,
            request_id=request_id,
            low_budget_mode=False,
            use_cache=False,
            bypass_anonymization=True,
            metadata={
                "n4_incremental_window": True,
                "prompt_version": self.prompt_version,
                "inventory_clause_count": len(inventory),
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
                content=_v2_provider_response(response.content),
                model_used=response.model_used,
                reported_cost_usd=str(response.cost_usd),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                provider_request_id=getattr(response, "request_id", None) or request_id,
            )
        return N4ProviderReceipt(
            content=_v2_provider_response(response.content),
            model_used=self.model_name,
            reported_cost_usd=str(Decimal(str(response.cost_usd))),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_request_id=getattr(response, "request_id", None) or request_id,
        )
