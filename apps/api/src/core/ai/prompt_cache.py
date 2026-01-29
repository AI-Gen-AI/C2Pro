"""
C2Pro - Prompt Cache

Sistema de caché para prompts idénticos usando hash SHA-256.

Características:
- Hash SHA-256 del input completo (prompt + system + parámetros)
- TTL de 24 horas
- Caché de respuestas completas de Claude
- Métricas de hit/miss
- Fallback a Redis o memoria

Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import structlog

from src.core.cache import CacheService, get_cache_service
from src.core.observability import record_cache_hit, record_cache_miss

logger = structlog.get_logger()

# ===========================================
# CONSTANTS
# ===========================================

CACHE_TYPE_PROMPT = "ai_prompt"
PROMPT_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 horas
PROMPT_CACHE_KEY_PREFIX = "prompt"


# ===========================================
# CACHE KEY GENERATION
# ===========================================


def build_prompt_hash(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    """
    Genera hash SHA-256 del input completo.

    El hash incluye todos los parámetros que afectan la respuesta:
    - prompt (user message)
    - system_prompt
    - temperature
    - max_tokens
    - model

    Args:
        prompt: Prompt del usuario
        system_prompt: System prompt (opcional)
        temperature: Temperatura del modelo
        max_tokens: Máximo de tokens de salida
        model: Nombre del modelo

    Returns:
        Hash SHA-256 hexadecimal (64 caracteres)

    Example:
        >>> hash1 = build_prompt_hash("Analiza este contrato", temperature=0.0)
        >>> hash2 = build_prompt_hash("Analiza este contrato", temperature=0.0)
        >>> hash1 == hash2
        True
        >>> hash3 = build_prompt_hash("Analiza este contrato", temperature=0.5)
        >>> hash1 == hash3
        False
    """
    # Crear dict con todos los parámetros
    cache_params = {
        "prompt": prompt,
        "system_prompt": system_prompt or "",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "model": model or "",
    }

    # Serializar a JSON determinístico (orden alfabético de keys)
    json_str = json.dumps(cache_params, sort_keys=True, ensure_ascii=True)

    # Generar hash SHA-256
    hash_bytes = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    logger.debug(
        "prompt_hash_generated",
        hash=hash_bytes[:16],  # Log solo primeros 16 chars
        prompt_length=len(prompt),
        has_system=bool(system_prompt),
        temperature=temperature,
    )

    return hash_bytes


def build_prompt_cache_key(prompt_hash: str) -> str:
    """
    Construye la key de Redis/cache para un prompt.

    Args:
        prompt_hash: Hash SHA-256 del prompt

    Returns:
        Key de cache con formato: "prompt:{hash}"

    Example:
        >>> key = build_prompt_cache_key("abc123...")
        >>> key
        'prompt:abc123...'
    """
    return f"{PROMPT_CACHE_KEY_PREFIX}:{prompt_hash}"


# ===========================================
# CACHE DATA STRUCTURES
# ===========================================


class CachedPromptResponse:
    """
    Respuesta cacheada de un prompt.

    Contiene toda la información necesaria para retornar
    una respuesta sin llamar a la API de Claude.
    """

    def __init__(
        self,
        content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cached_at: float,
        original_execution_time_ms: float,
    ):
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.cached_at = cached_at
        self.original_execution_time_ms = original_execution_time_ms

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict para guardar en cache."""
        return {
            "content": self.content,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "cached_at": self.cached_at,
            "original_execution_time_ms": self.original_execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedPromptResponse:
        """Deserializa desde dict del cache."""
        return cls(
            content=data["content"],
            model=data["model"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cost_usd=data["cost_usd"],
            cached_at=data["cached_at"],
            original_execution_time_ms=data["original_execution_time_ms"],
        )

    def get_age_seconds(self) -> float:
        """Retorna la edad del cache en segundos."""
        return time.time() - self.cached_at

    def is_expired(self, ttl_seconds: int = PROMPT_CACHE_TTL_SECONDS) -> bool:
        """Verifica si el cache expiró."""
        return self.get_age_seconds() > ttl_seconds


# ===========================================
# PROMPT CACHE SERVICE
# ===========================================


class PromptCacheService:
    """
    Servicio de caché para prompts de AI.

    Usa la infraestructura de CacheService existente (Redis + fallback memoria).

    Características:
    - Cache hit: Retorna respuesta inmediata sin llamar API
    - Cache miss: Marca para cachear después de llamar API
    - TTL de 24 horas
    - Métricas de hit/miss automáticas

    Uso:
        cache = PromptCacheService(cache_service)

        # Intentar obtener del cache
        cached = await cache.get_cached_response(
            prompt="Analiza este contrato...",
            system_prompt="Eres un experto...",
            temperature=0.0,
            model="claude-sonnet-4",
        )

        if cached:
            print("Cache HIT!")
            return cached
        else:
            # Cache MISS - llamar API
            response = await call_claude_api(...)

            # Guardar en cache
            await cache.set_cached_response(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                model=model,
                response=response,
            )
    """

    def __init__(self, cache_service: CacheService | None = None):
        """
        Inicializa el servicio de cache de prompts.

        Args:
            cache_service: Instancia de CacheService (si None, usa singleton)
        """
        self.cache_service = cache_service or get_cache_service()

        if self.cache_service is None:
            logger.warning(
                "prompt_cache_disabled",
                reason="cache_service_not_initialized",
            )

        self.enabled = self.cache_service is not None

    # ===========================================
    # GET CACHED RESPONSE
    # ===========================================

    async def get_cached_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> CachedPromptResponse | None:
        """
        Intenta obtener respuesta del cache.

        Args:
            prompt: Prompt del usuario
            system_prompt: System prompt (opcional)
            temperature: Temperatura del modelo
            max_tokens: Máximo de tokens
            model: Nombre del modelo

        Returns:
            CachedPromptResponse si hay cache hit, None si cache miss
        """
        if not self.enabled or not self.cache_service:
            return None

        # Generar hash del prompt
        prompt_hash = build_prompt_hash(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

        # Intentar obtener del cache
        cache_key = build_prompt_cache_key(prompt_hash)
        cached_data = await self.cache_service.get_json(cache_key)

        if cached_data is None:
            # Cache MISS
            record_cache_miss(CACHE_TYPE_PROMPT)
            logger.debug(
                "prompt_cache_miss",
                hash=prompt_hash[:16],
                prompt_length=len(prompt),
            )
            return None

        # Cache HIT
        try:
            cached_response = CachedPromptResponse.from_dict(cached_data)

            # Verificar si expiró (double-check)
            if cached_response.is_expired():
                logger.info(
                    "prompt_cache_expired",
                    hash=prompt_hash[:16],
                    age_seconds=cached_response.get_age_seconds(),
                )
                record_cache_miss(CACHE_TYPE_PROMPT)
                return None

            record_cache_hit(CACHE_TYPE_PROMPT)
            logger.info(
                "prompt_cache_hit",
                hash=prompt_hash[:16],
                age_seconds=cached_response.get_age_seconds(),
                model=cached_response.model,
                saved_cost_usd=cached_response.cost_usd,
            )

            return cached_response

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(
                "prompt_cache_decode_failed",
                hash=prompt_hash[:16],
                error=str(e),
            )
            record_cache_miss(CACHE_TYPE_PROMPT)
            return None

    # ===========================================
    # SET CACHED RESPONSE
    # ===========================================

    async def set_cached_response(
        self,
        prompt: str,
        response_content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        execution_time_ms: float,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        ttl_seconds: int = PROMPT_CACHE_TTL_SECONDS,
    ) -> None:
        """
        Guarda respuesta en cache.

        Args:
            prompt: Prompt del usuario
            response_content: Contenido de la respuesta
            model: Nombre del modelo usado
            input_tokens: Tokens de entrada
            output_tokens: Tokens de salida
            cost_usd: Costo en USD
            execution_time_ms: Tiempo de ejecución original
            system_prompt: System prompt (opcional)
            temperature: Temperatura del modelo
            max_tokens: Máximo de tokens
            ttl_seconds: TTL del cache (default 24h)
        """
        if not self.enabled or not self.cache_service:
            return

        # Generar hash del prompt
        prompt_hash = build_prompt_hash(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

        # Crear objeto cacheado
        cached_response = CachedPromptResponse(
            content=response_content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            cached_at=time.time(),
            original_execution_time_ms=execution_time_ms,
        )

        # Guardar en cache
        cache_key = build_prompt_cache_key(prompt_hash)
        await self.cache_service.set_json(
            key=cache_key,
            value=cached_response.to_dict(),
            ttl_seconds=ttl_seconds,
        )

        logger.info(
            "prompt_cached",
            hash=prompt_hash[:16],
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            ttl_hours=ttl_seconds / 3600,
        )

    # ===========================================
    # CACHE STATISTICS
    # ===========================================

    async def get_cache_stats(self) -> dict[str, Any]:
        """
        Obtiene estadísticas del cache de prompts.

        Returns:
            Dict con estadísticas (hit rate, etc.)
        """
        # TODO: Implementar contadores de hit/miss
        # Por ahora retorna info básica
        return {
            "enabled": self.enabled,
            "ttl_hours": PROMPT_CACHE_TTL_SECONDS / 3600,
            "cache_type": CACHE_TYPE_PROMPT,
        }

    # ===========================================
    # UTILITIES
    # ===========================================

    async def invalidate_cache(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> bool:
        """
        Invalida (elimina) una entrada del cache.

        Args:
            prompt: Prompt a invalidar
            system_prompt: System prompt
            temperature: Temperatura
            max_tokens: Máximo tokens
            model: Modelo

        Returns:
            True si se invalidó, False si no existía
        """
        if not self.enabled or not self.cache_service:
            return False

        prompt_hash = build_prompt_hash(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

        cache_key = build_prompt_cache_key(prompt_hash)

        # Verificar si existe antes de eliminar
        cached_data = await self.cache_service.get_json(cache_key)
        if cached_data is None:
            return False

        # TODO: Implementar delete en CacheService
        # Por ahora, setear con TTL de 0 segundos
        await self.cache_service.set_json(cache_key, {}, ttl_seconds=1)

        logger.info("prompt_cache_invalidated", hash=prompt_hash[:16])
        return True


# ===========================================
# SINGLETON INSTANCE
# ===========================================

_prompt_cache_service: PromptCacheService | None = None


def get_prompt_cache_service() -> PromptCacheService:
    """
    Obtiene instancia singleton del PromptCacheService.

    Returns:
        PromptCacheService configurado

    Uso:
        from src.core.ai.prompt_cache import get_prompt_cache_service

        cache = get_prompt_cache_service()
        cached = await cache.get_cached_response(...)
    """
    global _prompt_cache_service

    if _prompt_cache_service is None:
        cache_service = get_cache_service()
        _prompt_cache_service = PromptCacheService(cache_service)

    return _prompt_cache_service


# ===========================================
# CACHE-AWARE DECORATOR (opcional)
# ===========================================


def with_prompt_cache(func):
    """
    Decorator para funciones que llaman a Claude API.

    Automáticamente maneja cache hit/miss.

    Uso:
        @with_prompt_cache
        async def generate_text(prompt: str, model: str) -> str:
            # Esta función solo se ejecuta en cache miss
            response = await call_claude_api(prompt, model)
            return response

    TODO: Implementar decorator completo
    """
    # Por ahora, retorna la función sin modificar
    # En futuras versiones, implementar wrapping automático
    return func

