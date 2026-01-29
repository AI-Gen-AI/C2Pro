"""
C2Pro - AI Service

Servicio principal para interacción con Claude API (Anthropic).

Características:
- Model routing inteligente (Haiku/Sonnet/Opus)
- Budget control por tenant
- Cost tracking y logging
- Retry logic con exponential backoff
- Caching de respuestas
- Prompt registry versionado

Version: 1.0.0
"""

import json
import time
from typing import Any
from uuid import UUID

import anthropic
import structlog
from anthropic import Anthropic
from anthropic.types import Message
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import settings
from src.core.cache import get_cache_service
from src.core.exceptions import AIServiceError
from src.core.ai.model_router import (
    ModelTier,
    TaskType,
    get_model_router,
)
from src.core.ai.prompt_cache import (
    get_prompt_cache_service,
)

logger = structlog.get_logger()


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class AIRequest:
    """Request para el servicio de AI."""

    def __init__(
        self,
        prompt: str,
        task_type: TaskType | str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        force_model_tier: ModelTier | None = None,
        document_hash: str | None = None,
        use_cache: bool = True,
        prompt_version: str | None = None,  # Para tracking (ai_usage_logs)
    ):
        self.prompt = prompt
        self.task_type = task_type
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.force_model_tier = force_model_tier
        self.document_hash = document_hash
        self.use_cache = use_cache
        self.prompt_version = prompt_version


class AIResponse:
    """Response del servicio de AI."""

    def __init__(
        self,
        content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cached: bool = False,
        execution_time_ms: float = 0,
        prompt_version: str | None = None,  # Versión del template usado
    ):
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.cached = cached
        self.execution_time_ms = execution_time_ms
        self.prompt_version = prompt_version


# ===========================================
# AI SERVICE
# ===========================================


class AIService:
    """
    Servicio principal para interacción con Claude API.

    Características:
    - Routing automático de modelos
    - Budget control
    - Cost tracking
    - Retry logic
    - Caching (TODO)

    Uso:
        service = AIService(
            anthropic_api_key="sk-ant-...",
            tenant_id=tenant_id,
        )

        response = await service.generate(
            request=AIRequest(
                prompt="Analiza este contrato...",
                task_type=TaskType.CONTRACT_PARSING,
            )
        )

        print(response.content)
        print(f"Cost: ${response.cost_usd:.4f}")
    """

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        tenant_id: UUID | None = None,
        budget_remaining_usd: float | None = None,
        wrapper: Any | None = None,
    ):
        """
        Inicializa el servicio de AI.

        Args:
            anthropic_api_key: API key de Anthropic (si None, usa settings)
            tenant_id: ID del tenant (para logging y budget)
            budget_remaining_usd: Budget restante del tenant
        """
        self.api_key = anthropic_api_key or settings.anthropic_api_key
        self.tenant_id = tenant_id
        self.budget_remaining_usd = budget_remaining_usd

        if not self.api_key:
            raise ValueError("Anthropic API key not configured")

        self.client = Anthropic(api_key=self.api_key)
        self.router = get_model_router()
        self.prompt_cache = get_prompt_cache_service()
        if wrapper is None:
            from src.core.ai.anthropic_wrapper import get_anthropic_wrapper

            self.wrapper = get_anthropic_wrapper()
        else:
            self.wrapper = wrapper

        logger.info(
            "ai_service_initialized",
            tenant_id=str(tenant_id) if tenant_id else None,
            budget_remaining=budget_remaining_usd,
            cache_enabled=self.prompt_cache.enabled if self.prompt_cache else False,
        )

    # ===========================================
    # MAIN METHODS
    # ===========================================

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:
        """
        Genera respuesta usando Claude API con caché automático.

        Orden de caché:
        1. Prompt cache (hash SHA-256 del input completo)
        2. Document extraction cache (por document_hash + task_type)
        3. API call (si ambos caches fallan)

        Args:
            request: Parámetros de la request

        Returns:
            AIResponse con el resultado

        Raises:
            ValueError: Si se excede el budget
            anthropic.APIError: Si hay error en la API
        """
        start_time = time.perf_counter()

        # ===========================================
        # CACHE LAYER 1: Prompt Cache (SHA-256)
        # ===========================================
        # Intenta obtener del caché de prompts idénticos
        if request.use_cache and self.prompt_cache and self.prompt_cache.enabled:
            # Necesitamos el modelo para el hash, pero aún no lo hemos seleccionado
            # Usamos una selección preliminar para el hash
            input_token_estimate = self._estimate_tokens(request.prompt)
            preliminary_model = self.router.select_model(
                task_type=request.task_type,
                input_token_estimate=input_token_estimate,
                budget_remaining_usd=self.budget_remaining_usd,
                force_tier=request.force_model_tier,
            )

            cached_response = await self.prompt_cache.get_cached_response(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                model=preliminary_model.name,
            )

            if cached_response:
                # Cache HIT - retornar respuesta inmediata
                execution_time_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "prompt_cache_used",
                    tenant_id=str(self.tenant_id) if self.tenant_id else None,
                    cached_age_seconds=cached_response.get_age_seconds(),
                    saved_cost_usd=cached_response.cost_usd,
                    saved_time_ms=cached_response.original_execution_time_ms - execution_time_ms,
                )
                return AIResponse(
                    content=cached_response.content,
                    model=cached_response.model,
                    input_tokens=cached_response.input_tokens,
                    output_tokens=cached_response.output_tokens,
                    cost_usd=0.0,  # No cost porque es cached
                    cached=True,
                    execution_time_ms=round(execution_time_ms, 2),
                    prompt_version=request.prompt_version,
                )

        # ===========================================
        # CACHE LAYER 2: Document Extraction Cache
        # ===========================================
        cache_service = get_cache_service()
        task_value = (
            request.task_type.value
            if isinstance(request.task_type, TaskType)
            else str(request.task_type)
        )
        if (
            cache_service
            and request.document_hash
            and task_value in (TaskType.SIMPLE_EXTRACTION.value, TaskType.COMPLEX_EXTRACTION.value)
        ):
            cached_payload = await cache_service.get_extraction(
                request.document_hash,
                task_value,
            )
            if cached_payload:
                execution_time_ms = (time.perf_counter() - start_time) * 1000
                return AIResponse(
                    content=cached_payload.get("content", ""),
                    model=cached_payload.get("model", ""),
                    input_tokens=cached_payload.get("input_tokens", 0),
                    output_tokens=cached_payload.get("output_tokens", 0),
                    cost_usd=cached_payload.get("cost_usd", 0.0),
                    cached=True,
                    execution_time_ms=round(execution_time_ms, 2),
                    prompt_version=request.prompt_version,
                )

        # ===========================================
        # NO CACHE - Llamar API
        # ===========================================

        # 1. Select model
        input_token_estimate = self._estimate_tokens(request.prompt)

        model_config = self.router.select_model(
            task_type=request.task_type,
            input_token_estimate=input_token_estimate,
            budget_remaining_usd=self.budget_remaining_usd,
            force_tier=request.force_model_tier,
        )

        # 2. Check budget (pre-flight)
        estimated_cost = self.router.estimate_cost(
            model=model_config,
            input_tokens=input_token_estimate,
            output_tokens=request.max_tokens or 4096,
        )

        if self.budget_remaining_usd is not None:
            if estimated_cost > self.budget_remaining_usd:
                raise ValueError(
                    f"Insufficient budget: ${self.budget_remaining_usd:.2f} remaining, "
                    f"estimated cost: ${estimated_cost:.4f}"
                )

        # 3. Prepare request
        max_tokens = request.max_tokens or model_config.max_tokens

        messages = [
            {
                "role": "user",
                "content": request.prompt,
            }
        ]

        # 4. Call API
        logger.info(
            "ai_request_started",
            tenant_id=str(self.tenant_id) if self.tenant_id else None,
            task_type=request.task_type
            if isinstance(request.task_type, str)
            else request.task_type.value,
            model=model_config.name,
            input_tokens_estimate=input_token_estimate,
        )

        try:
            response = self.client.messages.create(
                model=model_config.name,
                max_tokens=max_tokens,
                temperature=request.temperature,
                system=request.system_prompt or "",
                messages=messages,
            )

        except anthropic.APIError as e:
            logger.error(
                "ai_request_failed",
                error=str(e),
                model=model_config.name,
                tenant_id=str(self.tenant_id) if self.tenant_id else None,
            )
            raise

        # 5. Extract content
        content = self._extract_content(response)

        # 6. Calculate actual cost
        actual_cost = self.router.estimate_cost(
            model=model_config,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # 7. Log usage
        logger.info(
            "ai_request_completed",
            tenant_id=str(self.tenant_id) if self.tenant_id else None,
            task_type=request.task_type
            if isinstance(request.task_type, str)
            else request.task_type.value,
            model=model_config.name,
            prompt_version=request.prompt_version,  # CRÍTICO para auditoría
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=actual_cost,
            execution_time_ms=round(execution_time_ms, 2),
        )

        # 8. Save to prompt cache (SHA-256)
        if request.use_cache and self.prompt_cache and self.prompt_cache.enabled:
            await self.prompt_cache.set_cached_response(
                prompt=request.prompt,
                response_content=content,
                model=model_config.name,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=actual_cost,
                execution_time_ms=execution_time_ms,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

        # 9. Save to document extraction cache
        if (
            cache_service
            and request.document_hash
            and task_value in (TaskType.SIMPLE_EXTRACTION.value, TaskType.COMPLEX_EXTRACTION.value)
        ):
            await cache_service.set_extraction(
                request.document_hash,
                task_value,
                {
                    "content": content,
                    "model": model_config.name,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "cost_usd": actual_cost,
                },
            )

        # TODO: Guardar en tabla ai_usage_logs
        # await self._save_usage_log(
        #     tenant_id=self.tenant_id,
        #     project_id=None,  # Obtener del contexto si está disponible
        #     model=model_config.name,
        #     operation=request.task_type,
        #     prompt_version=request.prompt_version,  # ¡CRÍTICO para auditoría!
        #     input_tokens=response.usage.input_tokens,
        #     output_tokens=response.usage.output_tokens,
        #     cost_usd=actual_cost,
        #     cached=False,
        #     latency_ms=round(execution_time_ms, 2),
        # )

        return AIResponse(
            content=content,
            model=model_config.name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=actual_cost,
            cached=False,
            execution_time_ms=round(execution_time_ms, 2),
            prompt_version=request.prompt_version,
        )

    # ===========================================
    # GENERIC EXTRACTION (WRAPPER + RETRY + PARSING)
    # ===========================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIError)),
        reraise=True,
    )
    async def _call_wrapper(self, system_prompt: str, user_content: str) -> Any:
        from src.core.ai.anthropic_wrapper import AIRequest as WrapperRequest
        from src.core.ai.model_router import AITaskType

        request = WrapperRequest(
            prompt=user_content,
            system_prompt=system_prompt,
            task_type=AITaskType.COMPLEX_EXTRACTION,
            tenant_id=self.tenant_id,
            use_cache=True,
        )
        return await self.wrapper.generate(request)

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        """
        Runs an LLM extraction with retries, robust JSON parsing, and usage logging.

        Returns:
            Parsed JSON content (dict or list).
        """
        start_time = time.perf_counter()
        try:
            response = await self._call_wrapper(system_prompt, user_content)
        except RetryError as exc:
            raise AIServiceError(
                message="AI service temporarily unavailable. Please retry shortly."
            ) from exc
        except anthropic.APIError as exc:
            raise AIServiceError(
                message="AI service temporarily unavailable. Please retry shortly."
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

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def _estimate_tokens(self, text: str) -> int:
        """
        Estima tokens de un texto.

        Regla aproximada: 1 token ≈ 4 caracteres
        """
        return len(text) // 4

    def _extract_content(self, message: Message) -> str:
        """Extrae contenido de texto de la respuesta."""
        for block in message.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                return text

        return ""

    def _parse_json_response(self, raw: str) -> Any:
        """
        Robust JSON parsing for LLM responses with extra chatter.
        """
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        candidate = self._extract_json_block(raw)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise AIServiceError(message="Failed to parse AI JSON response.") from exc

    def _extract_json_block(self, raw: str) -> str:
        """
        Extracts the first JSON block (object or array) from a string.
        """
        start_idx = None
        stack = []
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

        # Fallback: best-effort slice using first/last braces.
        first = min(
            (idx for idx in (raw.find("{"), raw.find("[")) if idx != -1),
            default=-1,
        )
        last = max(raw.rfind("}"), raw.rfind("]"))
        if first != -1 and last != -1 and last > first:
            return raw[first : last + 1]

        raise AIServiceError(message="No JSON block found in AI response.")

    # ===========================================
    # BATCH PROCESSING
    # ===========================================

    async def generate_batch(
        self,
        requests: list[AIRequest],
    ) -> list[AIResponse]:
        """
        Procesa múltiples requests en batch.

        TODO: Implementar procesamiento paralelo con asyncio.gather
        """
        responses = []
        for request in requests:
            response = await self.generate(request)
            responses.append(response)

        return responses

    # ===========================================
    # BUDGET MANAGEMENT
    # ===========================================

    def check_budget_sufficient(
        self,
        task_type: TaskType,
        input_token_estimate: int,
        output_token_estimate: int = 4096,
    ) -> tuple[bool, float]:
        """
        Verifica si hay budget suficiente.

        Returns:
            (sufficient: bool, estimated_cost: float)
        """
        model_config = self.router.select_model(
            task_type=task_type,
            input_token_estimate=input_token_estimate,
            budget_remaining_usd=self.budget_remaining_usd,
        )

        estimated_cost = self.router.estimate_cost(
            model=model_config,
            input_tokens=input_token_estimate,
            output_tokens=output_token_estimate,
        )

        if self.budget_remaining_usd is None:
            return True, estimated_cost

        sufficient = estimated_cost <= self.budget_remaining_usd

        return sufficient, estimated_cost


# ===========================================
# FACTORY FUNCTION
# ===========================================


def create_ai_service(
    tenant_id: UUID,
    budget_remaining_usd: float | None = None,
) -> AIService:
    """
    Factory para crear instancia de AIService.

    Usa la API key de settings por defecto.

    Args:
        tenant_id: ID del tenant
        budget_remaining_usd: Budget restante (opcional)

    Returns:
        AIService configurado
    """
    return AIService(
        anthropic_api_key=settings.anthropic_api_key,
        tenant_id=tenant_id,
        budget_remaining_usd=budget_remaining_usd,
    )

