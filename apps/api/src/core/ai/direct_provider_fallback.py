"""Governed direct-provider fallback: no gateway, proxy, or OpenRouter.

This is the shared provider adapter for *already anonymized* LLM text.
Disabled unless explicitly configured and passed a durable reservation bound.
It never retries an ambiguous billable attempt or accepts a partial response.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
import structlog

from src.core.ai.llm_client import LLMPartialGenerationError, LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)
_MODEL_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{1,100}$")


class FallbackUnavailable(RuntimeError):
    """No approved direct provider remains with a verified cost ceiling."""


class ProviderUsageUnknown(RuntimeError):
    """The previous request may have been billed; operator reconciliation required."""


class ProviderRejected(RuntimeError):
    """The request was explicitly rejected before any generation took place."""

    def __init__(self, provider: str, status: int, reason: str) -> None:
        super().__init__(f"{provider}: provider rejected ({status}, {reason})")
        self.provider = provider
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class DirectRoute:
    provider: str
    model: str
    context_tokens: int
    output_tokens: int
    input_usd_m: Decimal
    output_usd_m: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectRoute":
        if data.get("provider") not in {"openai", "gemini"}:
            raise ValueError("Only direct OpenAI and Gemini providers are supported")
        model = data.get("model")
        if not isinstance(model, str) or not _MODEL_ID.fullmatch(model):
            raise ValueError("Unapproved or malformed provider model ID")
        # Model and cost assumptions must be supplied explicitly by Ops after
        # verification against the specific provider account.
        route = cls(
            provider=data["provider"],
            model=model,
            context_tokens=int(data["context_tokens"]),
            output_tokens=int(data["output_tokens"]),
            input_usd_m=Decimal(str(data["input_usd_m"])),
            output_usd_m=Decimal(str(data["output_usd_m"])),
        )
        if not (8192 <= route.context_tokens <= 2_000_000):
            raise ValueError("Context capacity is not verified")
        if not (1024 <= route.output_tokens <= 131_072):
            raise ValueError("Output capacity is not verified")
        if any(not x.is_finite() or x <= 0 for x in (route.input_usd_m, route.output_usd_m)):
            raise ValueError("Provider price must be a positive finite number")
        return route


def approved_routes(raw: str | None) -> tuple[DirectRoute, ...]:
    if not raw:
        return ()
    data = json.loads(raw)
    if not isinstance(data, list) or not 1 <= len(data) <= 2:
        raise ValueError("Expected one or two approved direct provider routes")
    routes = tuple(DirectRoute.from_dict(x) for x in data)
    if len({route.provider for route in routes}) != len(routes):
        raise ValueError("Fallback must use distinct direct providers")
    return routes


def safe_initial_fallback(error: Exception) -> bool:
    """Only explicit, non-billable provider rejection authorizes a new call."""
    import anthropic

    if isinstance(error, anthropic.AuthenticationError):
        return True
    if isinstance(error, anthropic.APIStatusError) and error.status_code == 402:
        return True
    if isinstance(error, anthropic.RateLimitError):
        return True
    if isinstance(error, anthropic.BadRequestError):
        response = getattr(error, "response", None)
        body = getattr(response, "text", "") if response is not None else ""
        # An arbitrary 400 might represent a malformed source or a model
        # mismatch. Require an explicit account/billing rejection.
        return any(
            indicator in body.lower()
            for indicator in ("credit balance", "insufficient credits", "insufficient_quota")
        )
    return False


def _cost(route: DirectRoute, input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * route.input_usd_m
        + Decimal(output_tokens) * route.output_usd_m
    ) / Decimal(1_000_000)


def _estimate_max_charge(route: DirectRoute, request: LLMRequest) -> Decimal:
    # Conservative character-count estimate is NOT a replacement for
    # provider token accounting: add safety margin, refuse oversize input.
    input_characters = sum(len(str(m.get("content") or "")) for m in request.messages)
    input_characters += len(request.system or "")
    estimated_input = max(1, input_characters * 4 + 2048)
    if estimated_input + request.max_tokens > route.context_tokens:
        raise FallbackUnavailable("Full source exceeds verified fallback context")
    if request.max_tokens > route.output_tokens:
        raise FallbackUnavailable("Requested output exceeds verified fallback capacity")
    return _cost(route, estimated_input, request.max_tokens) * Decimal("1.25")


def _rejection(status: int, provider: str, response: httpx.Response) -> ProviderRejected | ProviderUsageUnknown:
    # Never log the body: providers can echo source content. Text is consulted
    # solely for classifying whether the rejected call could be billed.
    text = response.text[:350].lower()
    if status in (401, 402, 403, 429):
        return ProviderRejected(provider, status, "credential_or_quota")
    if status == 400 and any(
        marker in text for marker in ("insufficient_quota", "credit balance", "billing")
    ):
        return ProviderRejected(provider, status, "billing_rejected")
    return ProviderUsageUnknown(f"{provider}: HTTP {status}; usage must be reconciled")


def _read_response(route: DirectRoute, payload: dict[str, Any]) -> tuple[str, int, int, str]:
    if route.provider == "openai":
        choices = payload.get("choices") or []
        if len(choices) != 1:
            raise ProviderUsageUnknown("OpenAI response has no single attributable completion")
        choice = choices[0]
        text = (choice.get("message") or {}).get("content")
        reason = str(choice.get("finish_reason") or "")
        usage = payload.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
    else:
        choices = payload.get("candidates") or []
        if len(choices) != 1:
            raise ProviderUsageUnknown("Gemini response has no single attributable completion")
        choice = choices[0]
        text = "".join(
            part.get("text", "")
            for part in (choice.get("content") or {}).get("parts", [])
            if isinstance(part, dict)
        )
        reason = str(choice.get("finishReason") or "")
        usage = payload.get("usageMetadata") or {}
        input_tokens = usage.get("promptTokenCount")
        # Gemini reasoning/thinking tokens can be billed as output even when
        # they do not appear in the text candidate.
        candidates = usage.get("candidatesTokenCount")
        thoughts = usage.get("thoughtsTokenCount", 0)
        output_tokens = (
            candidates + thoughts
            if type(candidates) is int and type(thoughts) is int and thoughts >= 0
            else None
        )
    if (
        not isinstance(text, str)
        or not text.strip()
        or type(input_tokens) is not int or type(output_tokens) is not int
        or input_tokens <= 0 or output_tokens < 0
    ):
        raise ProviderUsageUnknown("Provider output or token usage is missing")
    return text, input_tokens, output_tokens, reason


async def _invoke(
    route: DirectRoute,
    request: LLMRequest,
    *,
    key: str,
    client: httpx.AsyncClient,
) -> LLMResponse:
    if route.provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}"}
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)
        body = {
            "model": route.model,
            "messages": messages,
            "max_completion_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{route.model}:generateContent"
        headers = {"x-goog-api-key": key}
        body = {
            "contents": [
                {"role": "user", "parts": [{"text": str(msg.get("content") or "")}]}
                for msg in request.messages
            ],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.system:
            body["systemInstruction"] = {"parts": [{"text": request.system}]}
    began = time.monotonic()
    try:
        response = await client.post(url, headers=headers, json=body)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        # A timeout AFTER sending a request is not proof of zero provider usage.
        raise ProviderUsageUnknown(f"{route.provider}: ambiguous network failure") from exc
    if response.status_code >= 400:
        raise _rejection(response.status_code, route.provider, response)
    try:
        data = response.json()
        content, input_tokens, output_tokens, stop = _read_response(route, data)
    except (ValueError, TypeError, KeyError) as exc:
        raise ProviderUsageUnknown("Provider success lacked verifiable token/content data") from exc

    billed = _cost(route, input_tokens, output_tokens)
    if stop not in (("stop",) if route.provider == "openai" else ("STOP",)):
        raise LLMPartialGenerationError(
            "Direct-provider output incomplete; no generated analysis may be trusted",
            model=route.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=float(billed),
        )
    if (request.metadata or {}).get("full_source_analysis"):
        try:
            json.loads(content)
        except (ValueError, TypeError) as exc:
            raise LLMPartialGenerationError(
                "Full-source direct-provider output is not complete JSON",
                model=route.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=float(billed),
            ) from exc

    return LLMResponse(
        content=content,
        model=route.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=float(billed),
        request_id=request.request_id or "",
        execution_time_ms=(time.monotonic() - began) * 1000,
        retries=0,
        cached=False,
    )


async def fallback_after_unbilled_rejection(
    request: LLMRequest,
    original_error: Exception,
    *,
    routes: Sequence[DirectRoute] | None = None,
    key_lookup: Callable[[str], str | None] | None = None,
    client: httpx.AsyncClient | None = None,
) -> LLMResponse:
    """Attempt at most 2 different direct providers; no routing by raw text.

    Requires a pre-existing persisted escrow for the *whole* possible call.
    No automatic timeout/5xx fallbacks and no replays after billable partials.
    """
    if os.getenv("C2PRO_DIRECT_FALLBACK_ENABLED") != "1":
        raise original_error
    metadata = request.metadata or {}
    legacy = metadata.get("budgeted_legacy") is True
    n4 = (
        metadata.get("n4_incremental_window") is True
        and metadata.get("n4_reservation_committed") is True
    )
    if not (legacy ^ n4):
        raise FallbackUnavailable("Exactly one persisted AI escrow authority required")
    if request.tenant_id is None:
        raise FallbackUnavailable("Tenant-scoped AI escrow identity required")
    if n4:
        from uuid import UUID
        try:
            UUID(str(request.request_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise FallbackUnavailable("N4 must use its committed reservation UUID") from exc
    if not safe_initial_fallback(original_error):
        raise original_error
    if routes is None:
        routes = approved_routes(os.getenv("C2PRO_DIRECT_FALLBACK_ROUTES"))
    if not routes:
        raise FallbackUnavailable("No authorized direct provider routes configured")
    try:
        reserve_key = "n4_reserved_usd" if n4 else "fallback_reserved_usd"
        remaining_budget = Decimal(str(metadata[reserve_key]))
    except (KeyError, ValueError, TypeError) as exc:
        raise FallbackUnavailable("Persisted fallback escrow amount required") from exc
    if not remaining_budget.is_finite() or remaining_budget <= 0:
        raise FallbackUnavailable("Fallback escrow must be positive and finite")

    def default_key(provider: str) -> str | None:
        return os.getenv("OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY")

    fetch_key = key_lookup or default_key
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15), follow_redirects=False)
    last_error: Exception = original_error
    try:
        for route in routes:
            # No speculative call when provider capacity or budget unverified.
            # Skip an incompatible route and consider a distinct approved one.
            try:
                estimate = _estimate_max_charge(route, request)
            except FallbackUnavailable:
                logger.warning(
                    "direct_fallback_route_skipped",
                    request_id=request.request_id,
                    provider=route.provider,
                    reason="capacity_unverified_or_insufficient",
                )
                continue
            if estimate > remaining_budget:
                logger.warning(
                    "direct_fallback_route_skipped",
                    request_id=request.request_id,
                    provider=route.provider,
                    reason="escrow_insufficient",
                )
                continue
            key = fetch_key(route.provider)
            if not key or len(key) < 20:
                logger.warning(
                    "direct_fallback_route_skipped",
                    request_id=request.request_id,
                    provider=route.provider,
                    reason="api_key_missing",
                )
                continue
            try:
                result = await _invoke(route, request, key=key, client=client)
            except ProviderRejected as exc:
                last_error = exc
                logger.warning(
                    "direct_fallback_provider_rejected",
                    request_id=request.request_id,
                    provider=route.provider,
                    model=route.model,
                    reason=exc.reason,
                    status=exc.status,
                )
                continue
            except (ProviderUsageUnknown, LLMPartialGenerationError):
                # Cost could already have occurred: do not call another model.
                raise
            if Decimal(str(result.cost_usd)) > remaining_budget:
                raise ProviderUsageUnknown("Provider cost exceeded the held escrow")
            logger.info(
                "direct_fallback_succeeded",
                request_id=request.request_id,
                tenant_id=str(request.tenant_id),
                provider=route.provider,
                model=route.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
                latency_ms=result.execution_time_ms,
            )
            return result
    finally:
        if owns_client:
            await client.aclose()
    raise FallbackUnavailable("Approved direct providers exhausted or unavailable") from last_error
