"""
C2Pro - Anthropic Wrapper (Main AI Client Interface)

Wrapper inteligente que integra:
- Model Router: Selección automática de modelos según task type
- Cache Service: Caché de respuestas con TTL
- LLM Client: Retry logic con exponential backoff
- Observability: Tracking completo de tokens, costos, latencia

Esta es la INTERFAZ PRINCIPAL recomendada para todas las llamadas a LLM.
NO usar directamente LLMClient o service.py. Usar este wrapper.

Version: 1.0.0
ROADMAP: §3.2 (Model Routing) + CE-S2-007
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message

from src.config import settings
from src.core.cache import get_cache_service
from src.core.ai.llm_client import LLMClient, LLMRequest
from src.core.ai.model_router import AITaskType, ModelConfig, ModelTier, get_model_router
from src.core.privacy.anonymizer import get_anonymizer as get_pii_anonymizer_service, PiiAnonymizerService


logger = structlog.get_logger()

# ===========================================
# CONSTANTS
# ===========================================

# Cache TTL por tipo de tarea (segundos)
CACHE_TTL_CONTRACT_EXTRACTION = 60 * 60 * 24 * 7  # 7 días (estable)
CACHE_TTL_STAKEHOLDER_CLASSIFICATION = 60 * 60 * 24  # 1 día
CACHE_TTL_COHERENCE_CHECK = 60 * 30  # 30 minutos
CACHE_TTL_RACI_GENERATION = 60 * 60  # 1 hora
CACHE_TTL_DEFAULT = 60 * 60  # 1 hora por defecto

# Default parameters
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.0

# Separator for combining prompts before anonymization
PROMPT_SEPARATOR = "\n<C2PRO_PROMPT_SEPARATOR>\n"


# ===========================================
# DATA STRUCTURES
# ===========================================


@dataclass
class AIRequest:
    """
    Request para el wrapper de Anthropic.

    Parámetros principales:
    - prompt: El texto del prompt
    - task_type: Tipo de tarea (determina el modelo a usar)
    - low_budget_mode: Activar optimización de costos

    Parámetros opcionales:
    - system_prompt: System prompt específico
    - max_tokens: Override del max_tokens del modelo
    - temperature: Override de temperatura
    - force_model_tier: Forzar un tier específico (testing)
    - tenant_id: ID del tenant (para tracking y rate limiting)
    - use_cache: Habilitar caché de respuestas
    - cache_ttl: TTL personalizado para caché
    - bypass_anonymization: Omitir el proceso de anonimización (usar con precaución)
    """

    prompt: str
    task_type: AITaskType | str

    # Budget optimization
    low_budget_mode: bool = False

    # Optional parameters
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: float = DEFAULT_TEMPERATURE
    force_model_tier: Optional[ModelTier] = None

    # Tracking
    tenant_id: Optional[UUID] = None
    request_id: str = field(default_factory=lambda: str(uuid4()))

    # Caching
    use_cache: bool = True
    cache_ttl: Optional[int] = None
    
    # Security
    bypass_anonymization: bool = False

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Convert string task_type to AITaskType."""
        if isinstance(self.task_type, str):
            self.task_type = AITaskType(self.task_type)


@dataclass
class AIResponse:
    """
    Response del wrapper de Anthropic.

    Incluye toda la información necesaria para observabilidad:
    - content: Texto generado
    - model_used: Modelo que procesó la request
    - usage: Tokens usados (input/output)
    - cost_usd: Costo calculado
    - latency_ms: Tiempo de ejecución
    - cached: Flag si vino de caché
    - request_id: ID para tracking
    """

    content: str
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float

    # Status flags
    cached: bool = False
    retries: int = 0

    # Tracking
    request_id: str = ""
    task_type: str = ""

    # Raw response (opcional)
    raw_response: Optional[Message] = None

    @property
    def usage(self) -> dict[str, int]:
        """Diccionario de usage (compatible con API de Anthropic)."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    @property
    def total_tokens(self) -> int:
        """Total de tokens usados."""
        return self.input_tokens + self.output_tokens


# ===========================================
# ANTHROPIC WRAPPER
# ===========================================


class AnthropicWrapper:
    """
    Wrapper inteligente para Claude API con integración completa.

    Características:
    ✅ Model Routing automático según task type (ROADMAP §3.2)
    ✅ Low budget mode con degradación inteligente
    ✅ Cache de respuestas con TTL configurable
    ✅ Retry con exponential backoff (via LLMClient)
    ✅ Circuit breaker para protección
    ✅ Observabilidad completa (tokens, costos, latencia)
    ✅ Logging estructurado
    ✅ Anonimización automática de PII (Gate 8)

    Uso básico:
        wrapper = AnthropicWrapper()

        request = AIRequest(
            prompt="Extrae las cláusulas del contrato...",
            task_type=AITaskType.CONTRACT_EXTRACTION,
            tenant_id=tenant_id
        )

        response = await wrapper.generate(request)

        print(f"Respuesta: {response.content}")
        print(f"Modelo usado: {response.model_used}")
        print(f"Costo: ${response.cost_usd:.6f}")
        print(f"Tokens: {response.total_tokens}")
        print(f"Latencia: {response.latency_ms}ms")
        print(f"Desde caché: {response.cached}")

    Uso con low budget mode:
        request = AIRequest(
            prompt="Clasifica este stakeholder...",
            task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
            low_budget_mode=True  # Degradar a Haiku si es posible
        )

        response = await wrapper.generate(request)
        # Usará Haiku en lugar de Sonnet si la tarea lo permite
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        enable_cache: bool = True,
        enable_retry: bool = True,
        max_retries: int = 3,
    ):
        """
        Inicializa el wrapper de Anthropic.

        Args:
            api_key: API key de Anthropic (si None, usa settings)
            enable_cache: Habilitar caché de respuestas
            enable_retry: Habilitar retry logic
            max_retries: Número máximo de reintentos
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")

        self.enable_cache = enable_cache
        self.enable_retry = enable_retry

        # Initialize dependencies
        self.model_router = get_model_router()
        self.cache_service = get_cache_service() if enable_cache else None
        self.llm_client = LLMClient(api_key=self.api_key, max_retries=max_retries)
        self.anonymizer_service: PiiAnonymizerService = get_pii_anonymizer_service()

        # Initialize async client for direct calls
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        # Statistics
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_cost_usd = 0.0

        logger.info(
            "anthropic_wrapper_initialized",
            enable_cache=enable_cache,
            enable_retry=enable_retry,
            max_retries=max_retries,
            anonymizer_enabled=True,
        )

    # ===========================================
    # MAIN METHOD
    # ===========================================

    async def generate(self, request: AIRequest) -> AIResponse:
        """
        Genera respuesta del LLM con anonimización, routing, caché y retry.
        """
        start_time = time.perf_counter()
        self.total_requests += 1

        logger.info(
            "anthropic_wrapper_request_started",
            request_id=request.request_id,
            task_type=request.task_type.value,
            tenant_id=str(request.tenant_id) if request.tenant_id else None,
            low_budget_mode=request.low_budget_mode,
            use_cache=request.use_cache,
        )

        # ===========================================
        # STEP 1: PII Anonymization (GATE 8)
        # ===========================================
        
        deanonymization_map = {}
        safe_prompt = request.prompt
        safe_system_prompt = request.system_prompt

        if not request.bypass_anonymization:
            try:
                full_prompt = f"{request.system_prompt or ''}{PROMPT_SEPARATOR}{request.prompt}"
                anonymized_payload = self.anonymizer_service.anonymize(full_prompt)
                
                deanonymization_map = anonymized_payload.deanonymization_map
                safe_full_prompt = anonymized_payload.text
                
                safe_system_prompt, safe_prompt = safe_full_prompt.split(PROMPT_SEPARATOR, 1)

                if deanonymization_map:
                    logger.info(
                        "pii_anonymization_applied",
                        request_id=request.request_id,
                        entities_found=len(deanonymization_map)
                    )
            except Exception as e:
                logger.error("pii_anonymization_failed", request_id=request.request_id, error=str(e))
                # Re-raise as a security exception to halt the process
                raise e

        # ===========================================
        # STEP 2: Model Selection
        # ===========================================

        model_config = self.model_router.select_model_with_budget_mode(
            task_type=request.task_type,
            low_budget_mode=request.low_budget_mode,
            input_token_estimate=len(safe_prompt) // 4,  # Use safe prompt for estimate
            force_tier=request.force_model_tier,
        )

        max_tokens = request.max_tokens or model_config.max_tokens

        logger.info(
            "model_selected",
            request_id=request.request_id,
            model=model_config.name,
            tier=model_config.tier.value,
            max_tokens=max_tokens,
            temperature=request.temperature,
        )

        # ===========================================
        # STEP 3: Check Cache
        # ===========================================

        cache_key = None
        if request.use_cache and self.cache_service:
            cache_key = self._build_cache_key(
                prompt=safe_prompt, # Use safe prompt for cache key
                system_prompt=safe_system_prompt or "",
                model=model_config.name,
                temperature=request.temperature,
                max_tokens=max_tokens,
            )
            cached_response = await self._get_from_cache(cache_key)

            if cached_response:
                self.cache_hits += 1
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info("anthropic_wrapper_cache_hit", request_id=request.request_id, latency_ms=round(latency_ms, 2))

                # De-anonymize cached content
                rehydrated_content = cached_response["content"]
                if deanonymization_map:
                    for token, original in deanonymization_map.items():
                        rehydrated_content = rehydrated_content.replace(token, original)

                return AIResponse(
                    content=rehydrated_content,
                    model_used=cached_response["model"],
                    input_tokens=cached_response["input_tokens"],
                    output_tokens=cached_response["output_tokens"],
                    cost_usd=cached_response["cost_usd"],
                    latency_ms=round(latency_ms, 2),
                    cached=True,
                    retries=0,
                    request_id=request.request_id,
                    task_type=request.task_type.value,
                )

            self.cache_misses += 1
            logger.info("anthropic_wrapper_cache_miss", request_id=request.request_id)

        # ===========================================
        # STEP 4: Call API
        # ===========================================

        llm_request = LLMRequest(
            model=model_config.name,
            messages=[{"role": "user", "content": safe_prompt}], # Use safe prompt
            system=safe_system_prompt, # Use safe system prompt
            max_tokens=max_tokens,
            temperature=request.temperature,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            task_type=request.task_type.value,
            metadata=request.metadata,
        )

        try:
            llm_response = await self.llm_client.generate(llm_request)
        except Exception as e:
            logger.error("anthropic_wrapper_api_call_failed", request_id=request.request_id, error=str(e))
            raise

        # ===========================================
        # STEP 5: De-anonymize (Rehydrate) Response
        # ===========================================
        
        rehydrated_content = llm_response.content
        if deanonymization_map:
            for token, original in deanonymization_map.items():
                rehydrated_content = rehydrated_content.replace(token, original)
            logger.info("pii_de-anonymization_complete", request_id=request.request_id)

        # ===========================================
        # STEP 6: Calculate Cost & Save to Cache
        # ===========================================

        cost_usd = self.model_router.estimate_cost(
            model=model_config,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )
        self.total_cost_usd += cost_usd

        if request.use_cache and self.cache_service and cache_key:
            # IMPORTANT: Cache the ANONYMIZED content, not the rehydrated content
            await self._save_to_cache(
                cache_key=cache_key,
                content=llm_response.content, # Caching the raw, anonymized response from the LLM
                model=model_config.name,
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                cost_usd=cost_usd,
                ttl=self._get_cache_ttl_for_task(request.task_type),
            )
            logger.info("anthropic_wrapper_cached_anonymized_response", request_id=request.request_id)

        # ===========================================
        # STEP 7: Return Response
        # ===========================================

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info("anthropic_wrapper_request_success", request_id=request.request_id, latency_ms=round(latency_ms, 2))

        return AIResponse(
            content=rehydrated_content, # Return the rehydrated content
            model_used=model_config.name,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            cost_usd=cost_usd,
            latency_ms=round(latency_ms, 2),
            cached=False,
            retries=llm_response.retries,
            request_id=request.request_id,
            task_type=request.task_type.value,
            raw_response=llm_response.raw_response,
        )

    # ===========================================
    # CACHE METHODS
    # ===========================================

    def _build_cache_key(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Construye cache key único basado en todos los parámetros relevantes.

        Usa SHA256 hash del prompt + parámetros para tener keys cortas y únicas.
        """
        # Create unique string from all parameters
        key_parts = [
            prompt,
            system_prompt,
            model,
            str(temperature),
            str(max_tokens),
        ]
        key_string = "|".join(key_parts)

        # Hash to get fixed-length key
        hash_object = hashlib.sha256(key_string.encode())
        hash_hex = hash_object.hexdigest()

        # Prefix with namespace
        return f"llm_response:{hash_hex}"

    async def _get_from_cache(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Obtiene respuesta del caché."""
        if not self.cache_service:
            return None

        try:
            cached = await self.cache_service.get_json(cache_key)
            return cached
        except Exception as e:
            logger.warning("cache_get_failed", error=str(e))
            return None

    async def _save_to_cache(
        self,
        cache_key: str,
        content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        ttl: int,
    ) -> None:
        """Guarda respuesta en caché."""
        if not self.cache_service:
            return

        try:
            cache_data = {
                "content": content,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "cached_at": time.time(),
            }

            await self.cache_service.set_json(cache_key, cache_data, ttl_seconds=ttl)
        except Exception as e:
            logger.warning("cache_save_failed", error=str(e))

    def _get_cache_ttl_for_task(self, task_type: AITaskType) -> int:
        """Obtiene TTL apropiado según el tipo de tarea."""
        ttl_map = {
            AITaskType.CONTRACT_EXTRACTION: CACHE_TTL_CONTRACT_EXTRACTION,
            AITaskType.STAKEHOLDER_CLASSIFICATION: CACHE_TTL_STAKEHOLDER_CLASSIFICATION,
            AITaskType.COHERENCE_CHECK: CACHE_TTL_COHERENCE_CHECK,
            AITaskType.RACI_GENERATION: CACHE_TTL_RACI_GENERATION,
        }
        return ttl_map.get(task_type, CACHE_TTL_DEFAULT)

    # ===========================================
    # STATISTICS
    # ===========================================

    def get_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas del wrapper."""
        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0
            else 0
        )

        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "llm_client_stats": self.llm_client.get_statistics(),
        }


# ===========================================
# SINGLETON INSTANCE
# ===========================================

_wrapper: Optional[AnthropicWrapper] = None


def get_anthropic_wrapper() -> AnthropicWrapper:
    """
    Obtiene instancia singleton del Anthropic Wrapper.

    Esta es la forma recomendada de obtener el wrapper.

    Returns:
        AnthropicWrapper configurado

    Example:
        from src.core.ai.anthropic_wrapper import get_anthropic_wrapper, AIRequest, AITaskType

        wrapper = get_anthropic_wrapper()

        request = AIRequest(
            prompt="Extrae las cláusulas...",
            task_type=AITaskType.CONTRACT_EXTRACTION
        )

        response = await wrapper.generate(request)
    """
    global _wrapper

    if _wrapper is None:
        _wrapper = AnthropicWrapper(
            enable_cache=True,
            enable_retry=True,
            max_retries=3,
        )

    return _wrapper


def reset_wrapper() -> None:
    """Reset singleton (útil para testing)."""
    global _wrapper
    _wrapper = None
