"""
Circuit Breaker Configuration.

Pydantic settings for configuring circuit breakers via environment variables.

Environment Variables:
    CB_ENABLE_CIRCUIT_BREAKERS: Enable/disable all circuit breakers (default: true)
    CB_OPENAI_FAILURE_THRESHOLD: Failures before opening OpenAI circuit (default: 5)
    CB_OPENAI_RECOVERY_TIMEOUT: Seconds to wait before recovery (default: 60)
    CB_REDIS_FAILURE_THRESHOLD: Failures before opening Redis circuit (default: 3)
    CB_REDIS_RECOVERY_TIMEOUT: Seconds to wait before recovery (default: 15)
    ... (see CircuitBreakerSettings for all options)

Usage:
    from src.core.resilience.config import get_circuit_breaker_settings

    settings = get_circuit_breaker_settings()
    if settings.enable_circuit_breakers:
        cb = CircuitBreakerRegistry.register(
            CircuitBreakerConfig(
                service_name="openai_embeddings",
                failure_threshold=settings.openai_failure_threshold,
                recovery_timeout=settings.openai_recovery_timeout,
            )
        )
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CircuitBreakerSettings(BaseSettings):
    """
    Circuit breaker configuration from environment variables.

    All settings can be overridden via environment variables with CB_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="CB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Global settings
    enable_circuit_breakers: bool = Field(
        default=True,
        description="Enable or disable all circuit breakers globally",
    )

    # Anthropic LLM
    anthropic_failure_threshold: int = Field(
        default=5,
        description="Failures before opening Anthropic circuit",
    )
    anthropic_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds to wait before testing Anthropic recovery",
    )

    # OpenAI Embeddings
    openai_failure_threshold: int = Field(
        default=5,
        description="Failures before opening OpenAI circuit",
    )
    openai_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds to wait before testing OpenAI recovery",
    )

    # Redis Cache
    redis_failure_threshold: int = Field(
        default=3,
        description="Failures before opening Redis circuit (fast recovery due to fallback)",
    )
    redis_recovery_timeout: float = Field(
        default=15.0,
        description="Seconds to wait before testing Redis recovery",
    )

    # Redis Event Bus
    redis_events_failure_threshold: int = Field(
        default=3,
        description="Failures before opening Redis events circuit",
    )
    redis_events_recovery_timeout: float = Field(
        default=15.0,
        description="Seconds to wait before testing Redis events recovery",
    )

    # Clerk JWKS
    clerk_failure_threshold: int = Field(
        default=3,
        description="Failures before opening Clerk JWKS circuit",
    )
    clerk_recovery_timeout: float = Field(
        default=30.0,
        description="Seconds to wait before testing Clerk recovery",
    )

    # Cloudflare R2 Storage
    r2_failure_threshold: int = Field(
        default=5,
        description="Failures before opening R2 storage circuit",
    )
    r2_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds to wait before testing R2 recovery",
    )

    # Neo4j Graph Database
    neo4j_failure_threshold: int = Field(
        default=5,
        description="Failures before opening Neo4j circuit",
    )
    neo4j_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds to wait before testing Neo4j recovery",
    )

    # LangSmith (optional observability - higher tolerance)
    langsmith_failure_threshold: int = Field(
        default=10,
        description="Failures before opening LangSmith circuit (high tolerance)",
    )
    langsmith_recovery_timeout: float = Field(
        default=120.0,
        description="Seconds to wait before testing LangSmith recovery",
    )


@lru_cache
def get_circuit_breaker_settings() -> CircuitBreakerSettings:
    """
    Get circuit breaker settings singleton.

    Returns:
        CircuitBreakerSettings instance (cached)
    """
    return CircuitBreakerSettings()
