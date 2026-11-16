"""Opt-in, fail-closed OpenAI/Gemini transport for N4 real-risk extraction.

Kept behind C2PRO_N4_PROVIDER so the existing Anthropic path stays unchanged.
No continuation loop, no source truncation, no automatic retries. API usage is
always explicitly preflighted with operator-supplied model rates and ceiling.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from src.core.ai.anthropic_wrapper import PROMPT_SEPARATOR, AIRequest, AIResponse
from src.core.ai.llm_client import LLMPartialGenerationError
from src.core.privacy.anonymizer import PiiAnonymizerService

logger = structlog.get_logger(__name__)
_ALLOWED_MODELS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class N4ExternalProviderConfigurationError(ValueError):
    """Unavailable, unsafe, or under-budgeted external provider configuration."""


@dataclass(frozen=True)
class N4ProviderConfig:
    provider: str
    model: str
    api_key: str
    max_output_tokens: int
    max_request_usd: float
    input_usd_per_m: float
    output_usd_per_m: float
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.provider not in {"openai", "gemini"}:
            raise N4ExternalProviderConfigurationError("N4_PROVIDER_NOT_SUPPORTED")
        if not _ALLOWED_MODELS.fullmatch(self.model):
            raise N4ExternalProviderConfigurationError("N4_MODEL_ID_INVALID")
        if not self.api_key:
            raise N4ExternalProviderConfigurationError("N4_API_KEY_MISSING")
        if not 256 <= self.max_output_tokens <= 32_768:
            raise N4ExternalProviderConfigurationError("N4_OUTPUT_CAP_INVALID")
        if not 0 < self.max_request_usd <= 25:
            raise N4ExternalProviderConfigurationError("N4_REQUEST_BUDGET_INVALID")
        if self.input_usd_per_m <= 0 or self.output_usd_per_m <= 0:
            raise N4ExternalProviderConfigurationError("N4_PRICE_RATE_MISSING")
        if not 5 <= self.timeout_seconds <= 600:
            raise N4ExternalProviderConfigurationError("N4_TIMEOUT_INVALID")

    @classmethod
    def from_environment(cls, provider: str) -> N4ProviderConfig:
        if os.getenv("C2PRO_N4_EXTERNAL_PROVIDER_ENABLED", "").lower() not in {"1", "true", "yes"}:
            raise N4ExternalProviderConfigurationError("N4_EXTERNAL_PROVIDER_NOT_ENABLED")
        prefix = "C2PRO_N4"
        try:
            return cls(
                provider=provider,
                model=os.environ[f"{prefix}_{provider.upper()}_MODEL"],
                api_key=os.environ.get(
                    "OPENAI_API_KEY" if provider == "openai" else "GOOGLE_API_KEY", ""
                ),
                max_output_tokens=int(os.environ[f"{prefix}_OUTPUT_MAX_TOKENS"]),
                max_request_usd=float(os.environ[f"{prefix}_MAX_REQUEST_USD"]),
                input_usd_per_m=float(os.environ[f"{prefix}_INPUT_USD_PER_M"]),
                output_usd_per_m=float(os.environ[f"{prefix}_OUTPUT_USD_PER_M"]),
                timeout_seconds=float(os.environ.get(f"{prefix}_TIMEOUT_SECONDS", "120")),
            )
        except (KeyError, ValueError) as exc:
            raise N4ExternalProviderConfigurationError(
                "N4_EXTERNAL_PROVIDER_CONFIG_INCOMPLETE"
            ) from exc


class N4ExternalProvider:
    """Compatible with BaseTool's AIRequest -> AIResponse generation seam."""

    def __init__(
        self,
        config: N4ProviderConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        anonymizer: Any | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._anonymizer = anonymizer or PiiAnonymizerService()

    def _max_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.config.input_usd_per_m
            + output_tokens * self.config.output_usd_per_m
        ) / 1_000_000

    @staticmethod
    def _estimated_input_tokens(system: str, prompt: str) -> int:
        # Conservative preflight for typical Latin-language text, not a provider token count.
        # A model response is never accepted based on this estimate alone.
        return (len(system) + len(prompt) + 1) // 2 + 1

    async def generate(self, request: AIRequest) -> AIResponse:
        started = time.perf_counter()
        if not (request.metadata or {}).get("full_source_analysis"):
            raise N4ExternalProviderConfigurationError("N4_SOURCE_SCOPE_REQUIRED")
        if request.bypass_anonymization:
            raise N4ExternalProviderConfigurationError("N4_PII_BOUNDARY_REQUIRED")

        # Preserve the same PII gate as AnthropicWrapper; any failure blocks the call.
        joined = f"{request.system_prompt or ''}{PROMPT_SEPARATOR}{request.prompt}"
        anonymized = self._anonymizer.anonymize_document(joined)
        parts = anonymized.anonymized_text.split(PROMPT_SEPARATOR)
        if len(parts) != 2:
            raise N4ExternalProviderConfigurationError("N4_PII_SPLIT_INVALID")
        safe_system, safe_prompt = parts
        limit = min(
            self.config.max_output_tokens, request.max_tokens or self.config.max_output_tokens
        )
        estimated_input = self._estimated_input_tokens(safe_system, safe_prompt)
        reserved = self._max_cost(estimated_input, limit)
        if reserved > self.config.max_request_usd:
            raise N4ExternalProviderConfigurationError("N4_REQUEST_BUDGET_PRECHECK_FAILED")

        if self.config.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent"
            headers = {"x-goog-api-key": self.config.api_key}
            payload: dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": safe_system}]},
                "contents": [{"role": "user", "parts": [{"text": safe_prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": limit,
                    "responseMimeType": "application/json",
                },
            }
        else:
            url = "https://api.openai.com/v1/responses"
            headers = {"Authorization": f"Bearer {self.config.api_key}"}
            payload = {
                "model": self.config.model,
                "store": False,
                "instructions": safe_system,
                "input": [{"role": "user", "content": safe_prompt}],
                "max_output_tokens": limit,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "n4_risks",
                        "strict": True,
                        "schema": _RISK_SCHEMA,
                    }
                },
            }

        # One call only; no hidden SDK retry or background continuation.
        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            transport=self._transport,
            follow_redirects=False,
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        if self.config.provider == "gemini":
            usage = body.get("usageMetadata") or {}
            input_tokens = int(usage.get("promptTokenCount") or 0)
            output_tokens = int(usage.get("candidatesTokenCount") or 0)
            candidates = body.get("candidates") or []
            candidate = candidates[0] if candidates else {}
            stop = candidate.get("finishReason")
            text = "".join(
                part.get("text", "")
                for part in (candidate.get("content") or {}).get("parts", [])
                if isinstance(part, dict)
            )
            completed = stop == "STOP" and bool(text)
        else:
            usage = body.get("usage") or {}
            input_tokens = int(usage.get("input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
            stop = body.get("status")
            text = "".join(
                item.get("text", "")
                for item in body.get("output", [])
                if item.get("type") == "message"
                for item in item.get("content", [])
                if item.get("type") == "output_text"
            )
            completed = stop == "completed" and bool(text)

        if input_tokens <= 0 or output_tokens <= 0:
            raise N4ExternalProviderConfigurationError("N4_PROVIDER_USAGE_MISSING")
        cost = self._max_cost(input_tokens, output_tokens)
        logger.info(
            "n4_external_provider_receipt",
            provider=self.config.provider,
            model=self.config.model,
            request_id=request.request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(cost, 7),
            reserved_usd=round(reserved, 7),
            completed=completed,
        )
        if not completed:
            raise LLMPartialGenerationError(
                "N4_PROVIDER_OUTPUT_INCOMPLETE",
                model=self.config.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

        # A malformed complete turn is billable too: preserve actual usage
        # and do not let validation retry the entire document.
        try:
            data = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise LLMPartialGenerationError(
                "N4_PROVIDER_JSON_INVALID",
                model=self.config.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("risks"), list):
            raise LLMPartialGenerationError(
                "N4_PROVIDER_JSON_ENVELOPE_INVALID",
                model=self.config.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )
        for marker, original in (anonymized.mapping or {}).items():
            text = text.replace(marker, original)

        return AIResponse(
            content=text,
            model_used=self.config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=(time.perf_counter() - started) * 1000,
            request_id=request.request_id,
            continuations=0,
        )


_RISK_FIELDS: dict[str, Any] = {
    "category": {
        "type": "string",
        "enum": ["LEGAL", "SCHEDULE", "QUALITY", "SCOPE", "TECHNICAL", "BUDGET"],
    },
    "title": {"type": "string"},
    "summary": {"type": "string"},
    "description": {"type": "string"},
    "probability": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
    "impact": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
    "mitigation_suggestion": {"type": "string"},
    "source_quote": {"type": "string"},
    "source_text_snippet": {"type": "string"},
    "clause_ref": {"type": ["string", "null"]},
}
_RISK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _RISK_FIELDS,
                "required": list(_RISK_FIELDS),
                "additionalProperties": False,
            },
        },
    },
    "required": ["risks"],
    "additionalProperties": False,
}


def get_n4_external_provider() -> N4ExternalProvider:
    provider = os.getenv("C2PRO_N4_PROVIDER", "anthropic").strip().lower()
    if provider not in {"gemini", "openai"}:
        raise N4ExternalProviderConfigurationError("N4_PROVIDER_NOT_SUPPORTED")
    return N4ExternalProvider(N4ProviderConfig.from_environment(provider))
