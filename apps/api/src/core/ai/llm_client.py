"""
C2Pro - LLM Client Wrapper

Wrapper robusto para Claude API (Anthropic) con:
- Retry con exponential backoff
- Logging estructurado completo
- Cost tracking automático
- Rate limit handling
- Circuit breaker pattern
- Error recovery

Version: 1.0.0
"""

from __future__ import annotations

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
    task_type: str | None = None

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
# CIRCUIT BREAKER
# ===========================================


class CircuitBreakerState(str, Enum):
    """Estados del circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern para proteger contra cascading failures.

    Después de N fallos consecutivos, "abre" el circuito y rechaza requests
    por un período de recovery. Luego intenta "half-open" para probar recovery.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.success_count_in_half_open = 0

    def record_success(self):
        """Registra un éxito."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count_in_half_open += 1
            if self.success_count_in_half_open >= 2:
                # Recovery exitoso
                self._close()
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count en éxito
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Registra un fallo."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self._open()

    def can_execute(self) -> bool:
        """Verifica si se puede ejecutar una request."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout elapsed
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time >= self.recovery_timeout
            ):
                self._half_open()
                return True
            return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def _open(self):
        """Abre el circuito (reject requests)."""
        self.state = CircuitBreakerState.OPEN
        logger.warning(
            "circuit_breaker_opened",
            failure_count=self.failure_count,
            threshold=self.failure_threshold,
        )

    def _half_open(self):
        """Semi-abre el circuito (test recovery)."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count_in_half_open = 0
        logger.info("circuit_breaker_half_open", testing_recovery=True)

    def _close(self):
        """Cierra el circuito (normal operation)."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count_in_half_open = 0
        logger.info("circuit_breaker_closed", recovered=True)

    def get_state(self) -> str:
        """Retorna el estado actual."""
        return self.state.value


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

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

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

    # ===========================================
    # MAIN METHOD
    # ===========================================

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
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            raise RuntimeError(
                f"Circuit breaker is {self.circuit_breaker.get_state()}, rejecting request"
            )

        # Track request
        self.total_requests += 1

        logger.info(
            "llm_request_started",
            request_id=request.request_id,
            tenant_id=str(request.tenant_id) if request.tenant_id else None,
            model=request.model,
            task_type=request.task_type,
            max_retries=self.max_retries,
        )

        retry_attempts: list[RetryAttempt] = []
        last_error: Exception | None = None

        # Retry loop
        for attempt in range(self.max_retries + 1):
            try:
                # Execute API call
                raw_response = self.client.messages.create(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    top_k=request.top_k,
                    stop_sequences=request.stop_sequences or [],
                    system=request.system or "",
                    messages=request.messages,
                )

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
                    self.circuit_breaker.record_success()

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
                    circuit_breaker_state=self.circuit_breaker.get_state()
                    if self.circuit_breaker
                    else None,
                )

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
                if self.circuit_breaker and error_type in [
                    LLMErrorType.SERVER_ERROR,
                    LLMErrorType.TIMEOUT,
                    LLMErrorType.CONNECTION,
                ]:
                    self.circuit_breaker.record_failure()

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

                # Wait before retry
                time.sleep(delay)

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
            circuit_breaker_state=self.circuit_breaker.get_state()
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

        Usa pricing hardcodeado. En producción, debería usar model_router.
        """
        # Simplified cost calculation
        # TODO: Integrate with model_router for accurate pricing
        if "haiku" in model.lower():
            input_cost = (input_tokens / 1_000_000) * 0.25
            output_cost = (output_tokens / 1_000_000) * 1.25
        elif "opus" in model.lower():
            input_cost = (input_tokens / 1_000_000) * 15.0
            output_cost = (output_tokens / 1_000_000) * 75.0
        else:  # Sonnet
            input_cost = (input_tokens / 1_000_000) * 3.0
            output_cost = (output_tokens / 1_000_000) * 15.0

        return round(input_cost + output_cost, 6)

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
