"""
AI Service Orchestrator.

High-level service that adds resilience, robust JSON parsing, and usage logging
on top of the Anthropic wrapper.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import structlog
from anthropic import APIError, RateLimitError
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.exceptions import AIServiceError
from src.modules.ai.anthropic_wrapper import AIRequest as WrapperRequest
from src.modules.ai.anthropic_wrapper import AnthropicWrapper, get_anthropic_wrapper
from src.modules.ai.model_router import AITaskType

logger = structlog.get_logger()


class AIService:
    """
    Orchestrator for AI calls with retry, parsing, and observability.
    """

    def __init__(self, wrapper: AnthropicWrapper | None = None, tenant_id: str | None = None) -> None:
        if os.getenv("C2PRO_AI_MOCK") == "1":
            self.wrapper = wrapper
        else:
            self.wrapper = wrapper or get_anthropic_wrapper()
        self.tenant_id = tenant_id

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        reraise=True,
    )
    async def _call_wrapper(self, system_prompt: str, user_content: str) -> Any:
        request = WrapperRequest(
            prompt=user_content,
            system_prompt=system_prompt,
            task_type=AITaskType.COMPLEX_EXTRACTION,
            tenant_id=self.tenant_id,
        )
        return await self.wrapper.generate(request)

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        """
        Runs an extraction with retries, robust JSON parsing, and usage logging.
        """
        start_time = time.perf_counter()
        if os.getenv("C2PRO_AI_MOCK") == "1":
            parsed = self._mock_extraction(system_prompt, user_content)
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "ai_usage_logged",
                timestamp=time.time(),
                model_used="mock",
                input_tokens=0,
                output_tokens=0,
                latency_ms=round(latency_ms, 2),
            )
            return parsed

        try:
            response = await self._call_wrapper(system_prompt, user_content)
        except RetryError as exc:
            raise AIServiceError(
                message="El servicio de IA está temporalmente no disponible."
            ) from exc
        except (RateLimitError, APIError) as exc:
            raise AIServiceError(
                message="El servicio de IA está temporalmente no disponible."
            ) from exc

        parsed = self._parse_json_response(response.content)

        latency_ms = response.latency_ms or (time.perf_counter() - start_time) * 1000
        logger.info(
            "ai_usage_logged",
            timestamp=time.time(),
            model_used=response.model_used,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=round(latency_ms, 2),
        )

        return parsed

    def _parse_json_response(self, raw: str) -> Any:
        raw = raw.strip()
        if not raw:
            raise AIServiceError(message="Failed to parse AI JSON response.")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        repaired = self._try_json_repair(raw)
        if repaired is not None:
            return repaired

        candidate = self._extract_json_block(raw)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        repaired = self._try_json_repair(candidate)
        if repaired is not None:
            return repaired

        raise AIServiceError(message="Failed to parse AI JSON response.")

    def _try_json_repair(self, payload: str) -> Any | None:
        try:
            import json_repair
        except ImportError:
            return None

        try:
            if hasattr(json_repair, "loads"):
                return json_repair.loads(payload)
            if hasattr(json_repair, "repair_json"):
                repaired = json_repair.repair_json(payload)
                return json.loads(repaired)
        except Exception:
            return None

        return None

    def _extract_json_block(self, raw: str) -> str:
        start_idx = None
        stack: list[str] = []
        for i, ch in enumerate(raw):
            if ch in "{[":
                if start_idx is None:
                    start_idx = i
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if stack and ch == stack[-1]:
                    stack.pop()
                    if not stack and start_idx is not None:
                        return raw[start_idx : i + 1]

        first = min(
            (idx for idx in (raw.find("{"), raw.find("[")) if idx != -1),
            default=-1,
        )
        last = max(raw.rfind("}"), raw.rfind("]"))
        if first != -1 and last != -1 and last > first:
            return raw[first : last + 1]

        raise AIServiceError(message="No JSON block found in AI response.")

    def _mock_extraction(self, system_prompt: str, user_content: str) -> Any:
        prompt = system_prompt.lower()
        if "riesgo" in prompt or "risk" in prompt:
            return [
                {
                    "title": "Penalizacion por retraso",
                    "description": "El contrato menciona penalizaciones por demora en plazos.",
                    "severity": "medium",
                    "confidence": 0.86,
                }
            ]
        return [
            {
                "code": "1.1",
                "name": "Planificacion y permisos",
                "description": "Actividades iniciales del proyecto.",
                "item_type": "work_package",
                "confidence": 0.84,
            }
        ]
