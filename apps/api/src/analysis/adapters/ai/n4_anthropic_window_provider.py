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
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.analysis.domain.n4_clause_inventory import (
    build_n4_clause_inventory,
    render_n4_clause_inventory_messages,
)
from src.analysis.domain.n4_compact_window_response import (
    EPC_CONTROL_DIMENSIONS,
    N4_WINDOW_PROMPT_VERSION,
    N4_WINDOW_SYSTEM_PROMPT,
    n4_window_source_message,
)
from src.analysis.domain.n4_retry_policy import N4RetryPolicy
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
                        "supporting_quotes", "severity_proposed", "epc_control_id",
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
                        "epc_control_id": {
                            "type": ["string", "null"],
                            "enum": [*EPC_CONTROL_DIMENSIONS, None],
                        },
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


_INVALID_TOOL_RESPONSE = '{"error":"INVALID_N4_TOOL_ENVELOPE"}'


def _v2_provider_response(raw: str, raw_response: object) -> str:
    """Fail closed unless exactly the intended Anthropic tool was invoked.

    LLMClient serializes tool *input* to content without the tool name, but
    AnthropicWrapper preserves the original Message in raw_response. Use that
    envelope as the source of identity; never infer tool identity from JSON.
    Return an invalid parser envelope (rather than raising) so the runner can
    settle already-accounted token usage and mark the window BLOCKED.
    """
    if getattr(raw_response, "stop_reason", None) != "tool_use":
        return _INVALID_TOOL_RESPONSE
    blocks = getattr(raw_response, "content", None)
    if not isinstance(blocks, (list, tuple)):
        return _INVALID_TOOL_RESPONSE
    # One and only one forced tool block: empty text/unknown blocks are not
    # proof of a valid tool response and must not be silently ignored.
    if len(blocks) != 1 or getattr(blocks[0], "type", None) != "tool_use":
        return _INVALID_TOOL_RESPONSE
    tool_block = blocks[0]
    if getattr(tool_block, "name", None) != "record_window_findings":
        return _INVALID_TOOL_RESPONSE
    tool_input = getattr(tool_block, "input", None)
    if not isinstance(tool_input, dict):
        return _INVALID_TOOL_RESPONSE
    try:
        content = json.loads(raw)
    except (TypeError, ValueError):
        return _INVALID_TOOL_RESPONSE
    if not isinstance(content, dict) or content != tool_input:
        return _INVALID_TOOL_RESPONSE
    normalized = dict(content)
    normalized["prompt_version"] = N4_WINDOW_PROMPT_VERSION
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


N4_INITIAL_OUTPUT_TOKENS = 8192
N4_RETRY_OUTPUT_TOKENS = 16384
N4_TIMEOUT_SECONDS = 300
N4_ESCROW_ESTIMATOR_VERSION = 'utf8-json-framing-v1'
N4_ESCROW_MARGIN = Decimal('1.25')
N4_FRAMING_TOKENS = 2048
N4_MONEY_SCALE = Decimal('0.000001')


class AnthropicN4WindowProvider:
    """Request bounded JSON, with NO full-source continuation or retry."""
    provider_name = "anthropic"
    prompt_version = N4_WINDOW_PROMPT_VERSION

    def __init__(
        self, *, wrapper: AnthropicWrapper,
        tier: ModelTier = ModelTier.STANDARD,
        max_output_tokens: int = N4_INITIAL_OUTPUT_TOKENS,
        fallback_reservation_usd: Decimal | str | None = None,
        escrow_preflight: tuple[Decimal, tuple[N4SourceWindow, ...]] | None = None,
        retry_policy: N4RetryPolicy | None = None,
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
        if retry_policy is not None:
            if type(retry_policy) is not N4RetryPolicy:
                raise ValueError("N4 explicit versioned retry policy required")
            if escrow_preflight is None or escrow_preflight[0] != retry_policy.initial_usd:
                raise ValueError("N4 retry policy requires original A13 initial escrow")
            if self.fallback_reservation_usd is not None:
                raise ValueError("N4 candidate retry policy forbids fallback")
            if self.max_output_tokens != N4_INITIAL_OUTPUT_TOKENS:
                raise ValueError("N4 candidate retry policy requires 8192 initial tokens")
        self.retry_policy = retry_policy
        self.attempt_escrow_enabled = escrow_preflight is not None
        self.escrow_ceiling_usd = None
        self._pinned_escrow_policy = None
        if escrow_preflight is not None:
            reservation_usd, windows = escrow_preflight
            self.escrow_ceiling_usd = reservation_usd
            self._pinned_escrow_policy = json.loads(json.dumps(self._escrow_policy()))
            # The initial attempt has its own affordability check.
            # Do not require hypothetical retry funding to open a first call.
            self._validate_escrow(reservation_usd, windows, attempt=1)

    def _escrow_policy(self) -> dict:
        from src.core.ai.model_capabilities import full_document_capacity

        config = self.wrapper.model_router.configs[self.tier]
        context_cap, output_cap = full_document_capacity(config.name)
        input_rate = Decimal(str(config.cost_per_1m_input))
        output_rate = Decimal(str(config.cost_per_1m_output))
        if config.name != self.model_name:
            raise ValueError("N4 escrow model identity changed")
        if any(not rate.is_finite() or rate <= 0 for rate in (input_rate, output_rate)):
            raise ValueError("N4 verified positive rates required")
        if output_cap < N4_RETRY_OUTPUT_TOKENS:
            raise ValueError("N4 output exceeds verified model capacity")
        if (self.escrow_ceiling_usd is None or not self.escrow_ceiling_usd.is_finite()
                or self.escrow_ceiling_usd <= 0):
            raise ValueError("N4 positive finite escrow required")
        policy = {
            "estimator": N4_ESCROW_ESTIMATOR_VERSION,
            "model": config.name, "input_rate": str(input_rate), "output_rate": str(output_rate),
            "context_cap": context_cap, "output_cap": output_cap,
            "initial_output": self.max_output_tokens, "retry_output": N4_RETRY_OUTPUT_TOKENS,
            "ceiling": str(self.escrow_ceiling_usd), "margin": str(N4_ESCROW_MARGIN),
            "framing_tokens": N4_FRAMING_TOKENS,
            "fallback": str(self.fallback_reservation_usd),
            "tool_schema": _N4_TOOL, "system": N4_WINDOW_SYSTEM_PROMPT,
        }
        if self.retry_policy is not None:
            if (
                type(self.retry_policy) is not N4RetryPolicy
                or self.fallback_reservation_usd is not None
                or self.fallback_routes
                or self.wrapper.enable_retry is not False
                or self.wrapper.llm_client.max_retries != 0
                or self.wrapper.enable_cache is not False
                or self.wrapper.cache_service is not None
                or self.wrapper.max_tokens_limit != N4_RETRY_OUTPUT_TOKENS
                or self.wrapper.llm_client.timeout_seconds != N4_TIMEOUT_SECONDS
                or self.max_output_tokens != N4_INITIAL_OUTPUT_TOKENS
            ):
                raise ValueError("N4 candidate transport policy mismatch")
            policy["retry_policy"] = self.retry_policy.identity()
        return policy

    def escrow_policy(self) -> dict:
        """Return a detached pinned policy; refuse mutable routing drift."""
        current = self._escrow_policy()
        if current != self._pinned_escrow_policy:
            raise ValueError("N4 escrow configuration changed")
        return current

    def estimate_attempt(self, window: N4SourceWindow, *, attempt: int) -> tuple[int, int, Decimal]:
        """Offline conservative estimate, not an invoice or tokenizer attestation.

        Count the entire losslessly serialized request (including system,
        inventory, schema, choice and JSON escaping) at one token per byte.
        This overestimates ordinary lossless byte-tokenization; 2048 extra
        tokens cover unobserved framing and a 25% financial margin remains.
        The actual provider tokenizer/framing must be independently qualified
        before runtime authorization; do not infer an unconditional API bound.
        """
        if type(attempt) is not int or attempt < 1:
            raise ValueError("N4 attempt must be positive and 1-based")
        policy = self.escrow_policy()
        cap = self.max_output_tokens if attempt == 1 else N4_RETRY_OUTPUT_TOKENS
        prompt, _ = self._window_prompt(window)
        payload = {
            "model": self.model_name, "max_tokens": cap, "temperature": 0.0,
            "stop_sequences": [], "system": N4_WINDOW_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [_N4_TOOL],
            "tool_choice": {"type": "tool", "name": "record_window_findings"},
        }
        # ensure_ascii=True also budgets JSON escapes, including non-ASCII.
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        input_tokens = len(encoded) + N4_FRAMING_TOKENS
        if input_tokens + cap > policy["context_cap"]:
            raise ValueError("N4 source exceeds verified model context")
        estimate = (
            Decimal(input_tokens) * Decimal(policy["input_rate"])
            + Decimal(cap) * Decimal(policy["output_rate"])
        ) / Decimal(1_000_000) * N4_ESCROW_MARGIN
        return input_tokens, cap, estimate.quantize(N4_MONEY_SCALE, rounding=ROUND_CEILING)

    def reservation_for_attempt(self, window: N4SourceWindow, *, attempt: int, ceiling: Decimal) -> Decimal:
        """Quote the exact attempt against the unchanged per-call ceiling."""
        if ceiling != self.escrow_ceiling_usd:
            raise ValueError("N4 runner escrow ceiling mismatch")
        _, _, estimate = self.estimate_attempt(window, attempt=attempt)
        effective_ceiling = (
            self.retry_policy.ceiling(attempt) if self.retry_policy is not None else ceiling
        )
        if estimate > effective_ceiling:
            raise ValueError("N4 worst-case charge exceeds existing per-window escrow")
        # Existing approved direct-fallback transport expects the full committed
        # escrow. Preserve that contract; do not increase any configured ceiling.
        return ceiling if self.fallback_reservation_usd is not None else estimate

    def _validate_escrow(
        self, reservation_usd: Decimal, windows: tuple[N4SourceWindow, ...], *, attempt: int = 1,
    ) -> None:
        if not windows:
            raise ValueError("N4 source windows required")
        for window in windows:
            self.reservation_for_attempt(window, attempt=attempt, ceiling=reservation_usd)

    @staticmethod
    def _window_prompt(window: N4SourceWindow) -> tuple[str, int]:
        inventory = build_n4_clause_inventory(window.context_text)
        inventory_context = "\n\n".join(render_n4_clause_inventory_messages(inventory))
        return n4_window_source_message(window) + "\n\n" + inventory_context, len(inventory)


    @classmethod
    def from_configured_account(
        cls, *, tier: ModelTier = ModelTier.STANDARD,
        max_output_tokens: int = N4_INITIAL_OUTPUT_TOKENS,
    ) -> AnthropicN4WindowProvider:
        return cls(
            wrapper=AnthropicWrapper(
                enable_cache=False,
                enable_retry=False,
                max_tokens_limit=N4_RETRY_OUTPUT_TOKENS,
                timeout_seconds=N4_TIMEOUT_SECONDS,
            ),
            tier=tier,
            max_output_tokens=max_output_tokens,
        )

    async def generate(
        self, *, window: N4SourceWindow, tenant_id: UUID, request_id: str,
        attempt: int = 1,
        reservation_usd: Decimal | None = None,
    ) -> N4ProviderReceipt:
        if self.prompt_version != N4_WINDOW_PROMPT_VERSION:
            raise ValueError("N4 provider prompt version differs from v2 contract")
        if attempt < 1:
            raise ValueError("N4 attempt must be positive and 1-based")
        output_cap = self.max_output_tokens if attempt == 1 else N4_RETRY_OUTPUT_TOKENS
        if self.attempt_escrow_enabled:
            required = self.reservation_for_attempt(
                window, attempt=attempt, ceiling=self.escrow_ceiling_usd,
            )
            if reservation_usd != required:
                raise ValueError("N4 exact committed attempt escrow required")
        prompt, inventory_count = self._window_prompt(window)
        if window.revision_id is None:
            raise ValueError("N4 source revision must be pinned")
        # Bypass re-anonymization ONLY because N4IncrementalRunner explicitly
        # requires an already N2-safe text projection. A second redaction pass
        # would otherwise invalidate source offsets and literal provenance.
        response = await self.wrapper.generate(AIRequest(
            prompt=prompt,
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
                "inventory_clause_count": inventory_count,
                **(
                    {"n4_disable_fallback": True, "n4_retry_policy_version": self.retry_policy.version}
                    if self.retry_policy is not None else {}
                ),
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
                content=_v2_provider_response(response.content, getattr(response, "raw_response", None)),
                model_used=response.model_used,
                reported_cost_usd=str(response.cost_usd),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                provider_request_id=getattr(response, "request_id", None) or request_id,
            )
        return N4ProviderReceipt(
            content=_v2_provider_response(response.content, getattr(response, "raw_response", None)),
            model_used=self.model_name,
            reported_cost_usd=str(Decimal(str(response.cost_usd))),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_request_id=getattr(response, "request_id", None) or request_id,
        )
