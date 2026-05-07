"""
C2Pro - LLM Client Wrapper

Wrapper robusto para Claude API (Anthropic) con:
- Retry con exponential backoff
- Logging estructurado completo
- Cost tracking automático
- Pre-execution token counting and cost estimation
- Rate limit handling
- Circuit breaker pattern (using centralized resilience infrastructure)
- Error recovery

Version: 1.2.0
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import anthropic
import structlog
from anthropic import Anthropic
from anthropic.types import Message

from src.config import settings
from src.core.ai.langsmith_client import LangSmithClient
from src.core.ai.model_router import ModelRouter, ModelTier
from src.core.ai.prompt_cache import (
    get_flash_cache_service,
)
from src.core.ai.token_counter import get_token_counter
from src.core.ai.usage_logger import AIUsageLogger
from src.core.observability import (
    record_ai_cache_hit,
    record_ai_cache_miss,
    record_ai_cache_size,
)
from src.core.observability.langsmith_decorator import traced_llm_call
from src.core.resilience import CircuitBreakerConfig, CircuitBreakerRegistry
from src.core.resilience.config import get_circuit_breaker_settings

logger = structlog.get_logger()

# ===========================================
# CONSTANTS
# ===========================================

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_RETRY_DELAY = 1.0  # seconds
DEFAULT_MAX_RETRY_DELAY = 32.0  # seconds
DEFAULT_BACKOFF_MULTIPLIER = 2.0

# Timeout configuration
DEFAULT_TIMEOUT_SECONDS = 120.0

# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60.0  # seconds


# ===========================================
# ERROR TYPES
# ===========================================


class LLMErrorType(str, Enum):
    """Tipos de errores del LLM."""

    RATE_LIMIT = "rate_limit"  # 429: Too many requests
    AUTHENTICATION = "authentication"  # 401: Invalid API key
    INVALID_REQUEST = "invalid_request"  # 400: Bad request
    NOT_FOUND = "not_found"  # 404: Model not found
    SERVER_ERROR = "server_error"  # 500+: Anthropic server error
    TIMEOUT = "timeout"  # Request timeout
    CONNECTION = "connection"  # Network error
    UNKNOWN = "unknown"  # Unknown error


# ===========================================
# DATA STRUCTURES
# ===========================================


@dataclass
class LLMRequest:
    """
    Request para el LLM client.

    Encapsula todos los parámetros de una llamada a Claude API.
    """

    model: str
    messages: list[dict[str, Any]]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] | None = None
    metadata: dict[str, Any] | None = None

    # Request tracking
    request_id: str | None = None
    tenant_id: UUID | None = None
    project_id: UUID | None = None
    task_type: str | None = None
    bypass_cache: bool = False
    tools: list[dict[str, Any]] | None = None

    def __post_init__(self):
        if self.request_id is None:
            self.request_id = str(uuid4())


@dataclass
class LLMResponse:
    """
    Response del LLM client.

    Incluye la respuesta completa más metadata de ejecución.
    """

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    # Execution metadata
    request_id: str
    execution_time_ms: float
    retries: int
    cached: bool = False

    # Raw response (opcional)
    raw_response: Message | None = None


@dataclass
class RetryAttempt:
    """Metadata de un intento de retry."""

    attempt: int
    error_type: LLMErrorType
    error_message: str
    delay_seconds: float
    timestamp: float


# ===========================================
# LLM CLIENT WRAPPER
# ===========================================


class LLMClient:
    """
    Wrapper robusto para Claude API con retry, logging, y cost tracking.

    Características:
    - Retry automático con exponential backoff
    - Logging estructurado de cada request/retry
    - Cost tracking por llamada
    - Rate limit handling inteligente
    - Circuit breaker para proteger contra failures
    - Timeout configurable

    Uso:
        client = LLMClient(api_key=settings.anthropic_api_key)

        request = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            tenant_id=tenant_id,
        )

        response = await client.generate(request)
        print(f"Response: {response.content}")
        print(f"Cost: ${response.cost_usd:.6f}")
        print(f"Retries: {response.retries}")
    """

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_retry_delay: float = DEFAULT_INITIAL_RETRY_DELAY,
        max_retry_delay: float = DEFAULT_MAX_RETRY_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        enable_circuit_breaker: bool = True,
    ):
        """
        Inicializa el LLM Client.

        Args:
            api_key: API key de Anthropic (si None, usa settings)
            max_retries: Máximo número de reintentos
            initial_retry_delay: Delay inicial para retry (segundos)
            max_retry_delay: Delay máximo para retry (segundos)
            backoff_multiplier: Multiplicador para exponential backoff
            timeout_seconds: Timeout por request (segundos)
            enable_circuit_breaker: Habilitar circuit breaker
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")

        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.backoff_multiplier = backoff_multiplier
        self.timeout_seconds = timeout_seconds

        # Initialize Anthropic client
        self.client = Anthropic(api_key=self.api_key, timeout=timeout_seconds)
        self.model_router = ModelRouter()

        # Observability clients
        self.langsmith_client = LangSmithClient()
        self.usage_logger = AIUsageLogger()
        self.flash_cache = get_flash_cache_service()

        # Circuit breaker (using centralized resilience infrastructure)
        self.circuit_breaker = self._init_circuit_breaker() if enable_circuit_breaker else None

        # Statistics
        self.total_requests = 0
        self.total_retries = 0
        self.total_cost_usd = 0.0

        logger.info(
            "llm_client_initialized",
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            circuit_breaker_enabled=enable_circuit_breaker,
        )


    def _init_circuit_breaker(self):
        """Initialize circuit breaker using centralized resilience infrastructure."""
        cb_settings = get_circuit_breaker_settings()
        if not cb_settings.enable_circuit_breakers:
            return None

        # Use the centralized registry with Anthropic-specific excluded exceptions
        return CircuitBreakerRegistry.register(
            CircuitBreakerConfig(
                service_name="anthropic_llm",
                failure_threshold=cb_settings.anthropic_failure_threshold,
                recovery_timeout=cb_settings.anthropic_recovery_timeout,
                # Don't trip circuit on client errors (auth, validation)
                excluded_exceptions=(
                    anthropic.AuthenticationError,
                    anthropic.BadRequestError,
                    anthropic.NotFoundError,
                ),
            )
        )

    # ===========================================
    # MAIN METHOD
    # ===========================================

    @traced_llm_call(task_type="llm_generation")
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Genera respuesta del LLM con retry automático.

        Args:
            request: LLMRequest con parámetros

        Returns:
            LLMResponse con resultado

        Raises:
            anthropic.APIError: Si todos los reintentos fallan
            RuntimeError: Si circuit breaker está abierto
        """
        start_time = time.perf_counter()

        # Check circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_execute_sync():
            raise RuntimeError(
                f"Circuit breaker is {self.circuit_breaker.state.value}, rejecting request"
            )

        # Track request
        self.total_requests += 1

        # TS-AI-FLASH-001: Check flash cache first
        tenant_id_str = str(request.tenant_id) if request.tenant_id else ""
        cached_entry = await self.flash_cache.get(
            model_id=request.model,
            system_prompt=request.system,
            messages=request.messages,
            tools=request.tools,
            temperature=request.temperature,
            bypass_cache=request.bypass_cache,
        )

        if cached_entry:
            # Cache hit - return cached response
            self.flash_cache._hits += 1
            record_ai_cache_hit(tenant_id_str, request.model)
            record_ai_cache_size(self.flash_cache.size)

            logger.info(
                "llm_cache_hit",
                request_id=request.request_id,
                model=request.model,
                original_cost_usd=cached_entry.cost_usd,
            )

            return LLMResponse(
                content=cached_entry.content,
                model=cached_entry.model,
                input_tokens=cached_entry.input_tokens,
                output_tokens=cached_entry.output_tokens,
                cost_usd=0.0,  # No cost for cached response
                request_id=cached_entry.request_id,
                execution_time_ms=0.0,  # Instant return
                retries=0,
                cached=True,
            )

        # Cache miss - proceed with normal flow
        record_ai_cache_miss(tenant_id_str, request.model)

        # Pre-execution token counting and cost estimation
        token_counter = get_token_counter()
        pre_estimate = token_counter.estimate_request(
            model=request.model,
            messages=request.messages,
            system=request.system,
            max_tokens=request.max_tokens,
        )

        logger.info(
            "llm_request_started",
            request_id=request.request_id,
            tenant_id=str(request.tenant_id) if request.tenant_id else None,
            model=request.model,
            task_type=request.task_type,
            max_retries=self.max_retries,
            # Pre-execution estimates
            estimated_input_tokens=pre_estimate.input_tokens,
            estimated_output_tokens=pre_estimate.estimated_output_tokens,
            estimated_cost_usd=pre_estimate.total_cost_usd,
            context_usage_percent=pre_estimate.context_usage_percent,
        )

        # Log warnings if context usage is high
        if pre_estimate.warnings:
            logger.warning(
                "llm_request_warnings",
                request_id=request.request_id,
                warnings=pre_estimate.warnings,
            )

        retry_attempts: list[RetryAttempt] = []
        last_error: Exception | None = None

        # Retry loop
        for attempt in range(self.max_retries + 1):
            try:
                # Execute API call
                # Build API call kwargs, excluding None values for top_p and top_k
                api_kwargs: dict[str, Any] = {
                    "model": request.model,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "stop_sequences": request.stop_sequences or [],
                    "system": request.system or "",
                    "messages": request.messages,
                }
                if request.top_p is not None:
                    api_kwargs["top_p"] = request.top_p
                if request.top_k is not None:
                    api_kwargs["top_k"] = request.top_k

                raw_response = self.client.messages.create(**api_kwargs)

                # Success!
                execution_time_ms = (time.perf_counter() - start_time) * 1000

                # Extract content
                content = self._extract_content(raw_response)

                # Calculate cost
                cost_usd = self._calculate_cost(
                    model=request.model,
                    input_tokens=raw_response.usage.input_tokens,
                    output_tokens=raw_response.usage.output_tokens,
                )

                # Update statistics
                self.total_cost_usd += cost_usd
                if attempt > 0:
                    self.total_retries += attempt

                # Record success in circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.record_success_sync()

                # Calculate estimation accuracy
                input_accuracy = (
                    (1 - abs(raw_response.usage.input_tokens - pre_estimate.input_tokens) /
                     max(raw_response.usage.input_tokens, 1)) * 100
                    if pre_estimate.input_tokens > 0 else 0
                )

                logger.info(
                    "llm_request_success",
                    request_id=request.request_id,
                    tenant_id=str(request.tenant_id) if request.tenant_id else None,
                    model=request.model,
                    input_tokens=raw_response.usage.input_tokens,
                    output_tokens=raw_response.usage.output_tokens,
                    cost_usd=cost_usd,
                    execution_time_ms=round(execution_time_ms, 2),
                    retries=attempt,
                    circuit_breaker_state=self.circuit_breaker.state.value
                    if self.circuit_breaker
                    else None,
                    # Pre-execution estimation vs actual
                    estimated_input_tokens=pre_estimate.input_tokens,
                    estimated_cost_usd=pre_estimate.total_cost_usd,
                    input_estimation_accuracy_pct=round(input_accuracy, 1),
                )

                # TS-AI-FLASH-001: Cache the response for future use
                await self.flash_cache.set(
                    model_id=request.model,
                    system_prompt=request.system,
                    messages=request.messages,
                    tools=request.tools,
                    temperature=request.temperature,
                    content=content,
                    input_tokens=raw_response.usage.input_tokens,
                    output_tokens=raw_response.usage.output_tokens,
                    cost_usd=cost_usd,
                    execution_time_ms=execution_time_ms,
                    request_id=request.request_id,
                )
                record_ai_cache_size(self.flash_cache.size)

                return LLMResponse(
                    content=content,
                    model=request.model,
                    input_tokens=raw_response.usage.input_tokens,
                    output_tokens=raw_response.usage.output_tokens,
                    cost_usd=cost_usd,
                    request_id=request.request_id,
                    execution_time_ms=round(execution_time_ms, 2),
                    retries=attempt,
                    raw_response=raw_response,
                )

            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)

                logger.warning(
                    "llm_request_attempt_failed",
                    request_id=request.request_id,
                    tenant_id=str(request.tenant_id) if request.tenant_id else None,
                    attempt=attempt + 1,
                    max_retries=self.max_retries + 1,
                    error_type=error_type.value,
                    error=str(e),
                )

                # Record failure in circuit breaker
                # The circuit breaker's excluded_exceptions config handles which
                # exceptions trip the circuit (AuthenticationError, BadRequestError, etc.)
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure_sync(e)

                # Check if we should retry
                if attempt >= self.max_retries:
                    break  # No more retries

                if not self._should_retry(error_type):
                    logger.error(
                        "llm_request_non_retryable_error",
                        request_id=request.request_id,
                        error_type=error_type.value,
                        error=str(e),
                    )
                    break  # Non-retryable error

                # Calculate retry delay (exponential backoff)
                delay = self._calculate_retry_delay(attempt, error_type)

                retry_attempts.append(
                    RetryAttempt(
                        attempt=attempt + 1,
                        error_type=error_type,
                        error_message=str(e),
                        delay_seconds=delay,
                        timestamp=time.time(),
                    )
                )

                logger.info(
                    "llm_request_retrying",
                    request_id=request.request_id,
                    attempt=attempt + 1,
                    delay_seconds=round(delay, 2),
                    error_type=error_type.value,
                )

                # Wait before retry (non-blocking)
                await asyncio.sleep(delay)

        # All retries exhausted
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        logger.error(
            "llm_request_failed",
            request_id=request.request_id,
            tenant_id=str(request.tenant_id) if request.tenant_id else None,
            model=request.model,
            total_attempts=len(retry_attempts) + 1,
            execution_time_ms=round(execution_time_ms, 2),
            final_error=str(last_error),
            circuit_breaker_state=self.circuit_breaker.state.value
            if self.circuit_breaker
            else None,
        )

        # Re-raise last error
        if last_error:
            raise last_error
        else:
            raise RuntimeError("LLM request failed with unknown error")

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def _extract_content(self, message: Message) -> str:
        """Extrae contenido de texto de la respuesta."""
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _classify_error(self, error: Exception) -> LLMErrorType:
        """Clasifica el tipo de error."""
        if isinstance(error, anthropic.RateLimitError):
            return LLMErrorType.RATE_LIMIT
        elif isinstance(error, anthropic.AuthenticationError):
            return LLMErrorType.AUTHENTICATION
        elif isinstance(error, anthropic.BadRequestError):
            return LLMErrorType.INVALID_REQUEST
        elif isinstance(error, anthropic.NotFoundError):
            return LLMErrorType.NOT_FOUND
        elif isinstance(error, anthropic.InternalServerError):
            return LLMErrorType.SERVER_ERROR
        elif isinstance(error, anthropic.APITimeoutError):
            return LLMErrorType.TIMEOUT
        elif isinstance(error, anthropic.APIConnectionError):
            return LLMErrorType.CONNECTION
        else:
            return LLMErrorType.UNKNOWN

    def _should_retry(self, error_type: LLMErrorType) -> bool:
        """Determina si se debe reintentar según el tipo de error."""
        retryable_errors = {
            LLMErrorType.RATE_LIMIT,  # Always retry rate limits
            LLMErrorType.SERVER_ERROR,  # Retry server errors
            LLMErrorType.TIMEOUT,  # Retry timeouts
            LLMErrorType.CONNECTION,  # Retry connection errors
        }
        return error_type in retryable_errors

    def _calculate_retry_delay(self, attempt: int, error_type: LLMErrorType) -> float:
        """
        Calcula el delay para el próximo retry usando exponential backoff.

        Rate limits tienen delays más largos.
        """
        base_delay = self.initial_retry_delay * (self.backoff_multiplier**attempt)

        # Rate limits necesitan delays más largos
        if error_type == LLMErrorType.RATE_LIMIT:
            base_delay *= 2

        # Cap at max delay
        delay = min(base_delay, self.max_retry_delay)

        # Add jitter (±20%)
        import random

        jitter = random.uniform(0.8, 1.2)
        delay *= jitter

        return delay

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calcula el costo de una llamada.
        """
        model_config = self.model_router.get_model_by_name(model)
        if model_config is None:
            lowered_model = model.lower()
            if "haiku" in lowered_model:
                model_config = self.model_router.get_model_by_tier(ModelTier.FLASH)
            elif "opus" in lowered_model:
                model_config = self.model_router.get_model_by_tier(ModelTier.POWERFUL)
            else:
                model_config = self.model_router.get_model_by_tier(ModelTier.STANDARD)
                logger.warning("llm_model_pricing_fallback", model=model, tier=ModelTier.STANDARD.value)

        return self.model_router.estimate_cost(model_config, input_tokens, output_tokens)

    # ===========================================
    # STATISTICS
    # ===========================================

    def get_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas del cliente."""
        avg_retries = self.total_retries / self.total_requests if self.total_requests > 0 else 0

        return {
            "total_requests": self.total_requests,
            "total_retries": self.total_retries,
            "total_cost_usd": round(self.total_cost_usd, 2),
            "avg_retries_per_request": round(avg_retries, 2),
            "circuit_breaker_state": self.circuit_breaker.get_state()
            if self.circuit_breaker
            else None,
            "circuit_breaker_failures": self.circuit_breaker.failure_count
            if self.circuit_breaker
            else None,
        }


# ===========================================
# FACTORY FUNCTION
# ===========================================


def create_llm_client(
    api_key: str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    enable_circuit_breaker: bool = True,
) -> LLMClient:
    """
    Factory para crear LLMClient.

    Args:
        api_key: API key de Anthropic (si None, usa settings)
        max_retries: Máximo de reintentos
        enable_circuit_breaker: Habilitar circuit breaker

    Returns:
        LLMClient configurado
    """
    return LLMClient(
        api_key=api_key,
        max_retries=max_retries,
        enable_circuit_breaker=enable_circuit_breaker,
    )
