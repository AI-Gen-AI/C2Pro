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

import time
from uuid import UUID

import anthropic
import structlog
from anthropic import Anthropic
from anthropic.types import Message, TextBlock

from src.config import settings
from src.modules.ai.model_router import (
    ModelTier,
    TaskType,
    get_model_router,
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
    ):
        self.prompt = prompt
        self.task_type = task_type
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.force_model_tier = force_model_tier


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
    ):
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.cached = cached
        self.execution_time_ms = execution_time_ms


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

        logger.info(
            "ai_service_initialized",
            tenant_id=str(tenant_id) if tenant_id else None,
            budget_remaining=budget_remaining_usd,
        )

    # ===========================================
    # MAIN METHODS
    # ===========================================

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:
        """
        Genera respuesta usando Claude API.

        Args:
            request: Parámetros de la request

        Returns:
            AIResponse con el resultado

        Raises:
            ValueError: Si se excede el budget
            anthropic.APIError: Si hay error en la API
        """
        start_time = time.perf_counter()

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
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=actual_cost,
            execution_time_ms=round(execution_time_ms, 2),
        )

        # TODO: Guardar en tabla ai_usage_logs
        # await self._save_usage_log(...)

        return AIResponse(
            content=content,
            model=model_config.name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=actual_cost,
            cached=False,  # TODO: implementar cache
            execution_time_ms=round(execution_time_ms, 2),
        )

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
            if isinstance(block, TextBlock):
                return block.text

        return ""

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
