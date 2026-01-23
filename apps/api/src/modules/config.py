"""
C2Pro API Configuration

Carga y valida todas las variables de entorno necesarias.
Usa Pydantic Settings para type-safety y validación.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación.

    Variables de entorno se cargan automáticamente.
    Prefijo: sin prefijo (carga directo de .env)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================
    # ENVIRONMENT
    # ===========================================
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ===========================================
    # API
    # ===========================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ===========================================
    # SUPABASE
    # ===========================================
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon/public key")
    supabase_service_key: str = Field(..., description="Supabase service role key")
    database_url: str = Field(..., description="PostgreSQL connection URL")

    # ===========================================
    # REDIS
    # ===========================================
    upstash_redis_url: str | None = None
    upstash_redis_token: str | None = None
    redis_url: str = "redis://localhost:6379"  # Fallback local

    @property
    def effective_redis_url(self) -> str:
        """Retorna URL de Redis (Upstash si disponible, sino local)."""
        if self.upstash_redis_url and self.upstash_redis_token:
            return self.upstash_redis_url
        return self.redis_url

    # ===========================================
    # CLOUDFLARE R2
    # ===========================================
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "c2pro-documents"
    r2_endpoint_url: str | None = None  # Para MinIO local
    r2_public_url: str | None = None

    @property
    def r2_endpoint(self) -> str:
        """Endpoint de R2 (o MinIO para local)."""
        if self.r2_endpoint_url:
            return self.r2_endpoint_url
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return "http://localhost:9000"  # MinIO local

    # ===========================================
    # ANTHROPIC
    # ===========================================
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    ai_default_model: str = "claude-3-5-sonnet-20241022"
    ai_fallback_model: str = "claude-3-haiku-20240307"
    ai_max_tokens: int = 4096
    ai_temperature: float = 0.1
    ai_monthly_budget_per_tenant: float = 50.0
    ai_alert_threshold: float = 0.8

    # ===========================================
    # SENTRY
    # ===========================================
    sentry_dsn: str | None = None

    # ===========================================
    # EMAIL
    # ===========================================
    resend_api_key: str | None = None
    email_from: str = "C2Pro <noreply@c2pro.app>"

    # ===========================================
    # SECURITY
    # ===========================================
    jwt_secret: str = Field(default="change-me-in-production", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # ===========================================
    # RATE LIMITING
    # ===========================================
    rate_limit_requests_per_minute: int = 60
    rate_limit_ai_requests_per_minute: int = 10

    # ===========================================
    # FILE UPLOAD
    # ===========================================
    max_file_size_mb: int = 50
    allowed_file_types: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".xlsx", ".xls", ".csv", ".bc3", ".mpp"]
    )

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def parse_file_types(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [ft.strip() for ft in v.split(",")]
        return v

    # ===========================================
    # FEATURE FLAGS
    # ===========================================
    feature_chat_enabled: bool = False
    feature_purchase_plan_enabled: bool = False
    feature_procore_integration: bool = False

    # ===========================================
    # COMPUTED PROPERTIES
    # ===========================================
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Obtiene settings cacheadas.

    Usar como dependencia en FastAPI:
        settings: Settings = Depends(get_settings)
    """
    return Settings()


# Instancia global para imports directos
settings = get_settings()
