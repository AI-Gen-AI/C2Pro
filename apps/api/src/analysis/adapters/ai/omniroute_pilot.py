"""Opt-in OmniRoute adapter for synthetic C2Pro EPC evaluation.

This adapter does not replace the Anthropic production client. It does not
retry, transfer actual project documents automatically, or invent provider prices.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

# Routes that returned short OmniRoute E2E responses on 2026-11-08.
# The two Antigravity aliases may share an upstream account and quota.
PILOT_MODELS: dict[str, str] = {
    "nvidia": "nvidia/nvidia/nemotron-3.5-bolt-e4b",
    "openrouter": "openrouter/liquid/lfm-3-1.7b:free",
    "gemini": "gemini/gemini-3.1-flash-lite",
    "grok-cli": "grok-cli/grok-4.7",
    "agy": "agy/claude-opus-4-6-thinking",
    "antigravity": "antigravity/claude-opus-4-6-thinking",
    "cursor": "cursor/auto-cost",
    "kiro": "kiro/claude-haiku-4.5",
}


class OmniRoutePilotError(RuntimeError):
    """Failure with no prompt, credential, or upstream body exposed."""

    def __init__(self, kind: str, status: int | None = None):
        self.kind = kind
        self.status = status
        super().__init__(f"omniroute_{kind}" + (f"_http_{status}" if status else ""))


@dataclass(frozen=True)
class PilotResult:
    content: str
    model_used: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    request_id: str
    task_type: str
    # Price is unknown until C2Pro has provider-specific cost attribution.
    cost_usd: float | None = None
    cached: bool = False
    retries: int = 0


def _gateway_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("OmniRoute base URL must be an HTTP(S) origin")
    if parts.username or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}:
        raise ValueError("OmniRoute base URL must not contain credentials, query or path")
    if parts.scheme == "http" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Remote OmniRoute origin requires HTTPS")
    return url


def _text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise OmniRoutePilotError("missing_choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise OmniRoutePilotError("missing_message")
    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        text = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
    else:
        text = ""
    if not text:
        raise OmniRoutePilotError("empty_response")
    return text


def _parse_json(text: str) -> dict[str, Any] | list[Any]:
    value = text.strip()
    fence = chr(96) * 3
    if value.startswith(fence) and value.endswith(fence):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {fence, fence + "json"}:
            value = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise OmniRoutePilotError("invalid_json") from exc
    if not isinstance(parsed, (dict, list)):
        raise OmniRoutePilotError("json_not_object")
    return parsed


class OmniRoutePilotClient:
    """Implements IAIClient.extract_json and the AIService.generate seam."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 40.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if model not in PILOT_MODELS.values():
            raise ValueError("Model is not in the verified pilot candidate list")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("OmniRoute client key is required")
        if not 1 <= timeout_seconds <= 150:
            raise ValueError("Timeout out of bounds")
        self.base_url = _gateway_url(base_url)
        self._api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    async def generate(self, request: Any) -> PilotResult:
        started = time.monotonic()
        messages: list[dict[str, str]] = []
        system_prompt = getattr(request, "system_prompt", None)
        if isinstance(system_prompt, str) and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        prompt = getattr(request, "prompt", "")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Pilot prompt must be a nonempty string")
        messages.append({"role": "user", "content": prompt})
        limit = getattr(request, "max_tokens", None) or 256
        if not isinstance(limit, int) or not 1 <= limit <= 8192:
            raise ValueError("Invalid max_tokens")
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": limit,
                        "stream": False,
                    },
                )
        except httpx.TimeoutException as exc:
            raise OmniRoutePilotError("timeout") from exc
        except httpx.HTTPError as exc:
            raise OmniRoutePilotError("transport") from exc
        if response.status_code != 200:
            raise OmniRoutePilotError("upstream", response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise OmniRoutePilotError("invalid_gateway_json") from exc
        if not isinstance(payload, dict):
            raise OmniRoutePilotError("invalid_gateway_json")
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        return PilotResult(
            content=_text(payload),
            model_used=self.model,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=round((time.monotonic() - started) * 1000, 1),
            request_id=str(getattr(request, "request_id", None) or uuid4()),
            task_type=str(getattr(request, "task_type", "")),
        )

    async def extract_json(
        self, system_prompt: str, user_content: str, task_type: str
    ) -> dict[str, Any] | list[Any]:
        from types import SimpleNamespace

        result = await self.generate(
            SimpleNamespace(
                system_prompt=system_prompt,
                prompt=user_content,
                # OpenRouter Liquid reported 256/256 completion tokens as
                # reasoning with no visible content during the first EPC run.
                # Give this model enough output budget for reasoning and JSON.
                max_tokens=1024 if self.model == PILOT_MODELS["openrouter"] else 256,
                task_type=task_type,
                request_id=str(uuid4()),
            )
        )
        return _parse_json(result.content)
