"""
C2Pro - Application Configuration

Configuración centralizada usando Pydantic Settings.
Soporta múltiples ambientes (dev, staging, prod).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de la aplicación.

    Las variables se cargan desde:
    1. Variables de entorno
    2. Archivo .env
    3. Valores por defecto
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ===========================================
    # GENERAL
    # ===========================================

    app_name: str = "C2Pro API"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = Field(default=False, description="Modo debug")

    # API Settings
    api_v1_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        description="Orígenes permitidos para CORS",
    )
    cors_credentials: bool = True
    cors_methods: list[str] = ["*"]
    cors_headers: list[str] = ["*"]

    # ===========================================
    # DATABASE (Supabase PostgreSQL)
    # ===========================================

    database_url: str = Field(..., description="PostgreSQL connection URL (asyncpg)")

    # Connection pool
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_pre_ping: bool = True
    db_echo: bool = Field(default=False, description="Log SQL queries")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Valida que la URL de base de datos sea PostgreSQL."""
        if v.startswith(("sqlite://", "sqlite+aiosqlite://")):
            return v
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("database_url must start with postgresql:// or postgresql+asyncpg://")
        return v

    # ===========================================
    # SECURITY
    # ===========================================

    # JWT (Supabase)
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon/public key")
    supabase_service_role_key: str = Field(..., description="Supabase service role key (admin)")

    # JWT Settings
    jwt_secret_key: str = Field(..., description="Secret key for JWT signing")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60 * 24, ge=1)  # 24 horas
    jwt_refresh_token_expire_days: int = Field(default=30, ge=1)

    # Password hashing
    bcrypt_rounds: int = Field(default=12, ge=10, le=14)

    # ===========================================
    # CACHE (Redis/Upstash)
    # ===========================================

    redis_url: str | None = Field(
        default=None, description="Redis connection URL (redis:// or rediss://)"
    )

    cache_ttl_default: int = Field(default=300, ge=0, description="TTL por defecto en segundos")
    cache_ttl_ai_response: int = Field(default=3600, ge=0, description="TTL para respuestas AI")

    # ===========================================
    # STORAGE (Cloudflare R2)
    # ===========================================

    storage_provider: Literal["r2", "s3", "local"] = "r2"

    # Cloudflare R2 / AWS S3
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "c2pro-documents"
    r2_endpoint_url: str | None = None  # Auto-construido si no se provee

    # Local storage (desarrollo)
    local_storage_path: str = str(Path(__file__).resolve().parents[2] / "storage")

    @property
    def storage_endpoint(self) -> str:
        """Construye el endpoint de R2 automáticamente."""
        if self.r2_endpoint_url:
            return self.r2_endpoint_url
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return ""

    # ===========================================
    # AI (Claude API - Anthropic)
    # ===========================================

    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key para Claude")

    # Model selection
    ai_model_default: str = "claude-sonnet-4-20250514"  # Sonnet 4 por defecto
    ai_model_fast: str = "claude-haiku-4-20250514"  # Haiku 4 para tareas rápidas
    ai_model_powerful: str = "claude-opus-4-20250514"  # Opus 4 para tareas complejas (Fase 2+)

    # Budget control
    ai_budget_monthly_default: float = Field(default=50.0, ge=0)  # USD por tenant
    ai_budget_warning_threshold: float = 0.8  # Alertar al 80%

    # Timeouts
    ai_timeout_seconds: int = Field(default=120, ge=10, le=600)
    ai_max_retries: int = Field(default=3, ge=0, le=5)

    # Token limits
    ai_max_tokens_output: int = Field(default=4096, ge=100, le=8192)

    # Cache
    ai_use_cache: bool = True
    ai_cache_ttl: int = Field(default=3600, ge=0)  # 1 hora

    # ===========================================
    # DOCUMENT PROCESSING
    # ===========================================

    # File upload limits
    max_upload_size_mb: int = Field(default=50, ge=1, le=200)
    allowed_document_types: list[str] = [".pdf", ".docx", ".xlsx", ".xls", ".bc3"]

    # PDF processing
    pdf_max_pages: int = Field(default=500, ge=1)

    # Excel processing
    excel_max_rows: int = Field(default=10000, ge=100)

    # ===========================================
    # OBSERVABILITY
    # ===========================================

    # Sentry
    sentry_dsn: str | None = Field(default=None, description="Sentry DSN para error tracking")
    sentry_environment: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0, le=1)

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = Field(default=True, description="Log en formato JSON")

    # ===========================================
    # EMAIL
    # ===========================================

    email_from: str = Field(
        default="C2Pro <noreply@c2pro.app>", validation_alias="EMAIL_FROM"
    )

    # ===========================================
    # RATE LIMITING
    # ===========================================

    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_per_hour: int = Field(default=1000, ge=1)
    rate_limit_user_per_min: int = Field(
        default=20, ge=1, validation_alias="RATE_LIMIT_USER_PER_MIN"
    )
    rate_limit_tenant_per_min: int = Field(
        default=60, ge=1, validation_alias="RATE_LIMIT_TENANT_PER_MIN"
    )

    # ===========================================
    # CELERY
    # ===========================================

    celery_task_always_eager: bool = Field(
        default=False, validation_alias="CELERY_TASK_ALWAYS_EAGER"
    )

    # ===========================================
    # BUDGET ALERTS (FINOPS)
    # ===========================================

    budget_alert_admin_emails: list[str] = Field(
        default_factory=list, validation_alias="BUDGET_ALERT_ADMIN_EMAILS"
    )
    budget_alert_webhook_url: str | None = Field(
        default=None, validation_alias="BUDGET_ALERT_WEBHOOK_URL"
    )

    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    smtp_from: str | None = Field(default=None, validation_alias="SMTP_FROM")

    # ===========================================
    # FEATURES FLAGS (MVP - Fase 1)
    # ===========================================

    feature_coherence_analysis: bool = True
    feature_wbs_generation: bool = True
    feature_bom_generation: bool = True
    feature_stakeholder_extraction: bool = True  # NUEVO v2.3.0
    feature_raci_generation: bool = False  # Fase 2
    feature_rfq_generation: bool = False  # Fase 2
    feature_expediting_vision: bool = False  # Fase 3

    # ===========================================
    # COMPUTED PROPERTIES
    # ===========================================

    @property
    def is_production(self) -> bool:
        """Verifica si está en producción."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Verifica si está en desarrollo."""
        return self.environment == "development"

    @property
    def max_upload_size_bytes(self) -> int:
        """Tamaño máximo de upload en bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def database_url_async(self) -> str:
        """URL de base de datos para asyncpg."""
        url = self.database_url
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ===========================================
    # VALIDATION
    # ===========================================

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            if not v.strip():  # Handle empty string
                return []
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ai_budget_monthly_default")
    @classmethod
    def validate_budget(cls, v: float) -> float:
        """Valida que el budget sea positivo."""
        if v < 0:
            raise ValueError("ai_budget_monthly_default must be >= 0")
        return v

    @field_validator("budget_alert_admin_emails", mode="before")
    @classmethod
    def parse_budget_alert_admin_emails(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [email.strip() for email in v.split(",") if email.strip()]
        return v


# ===========================================
# SINGLETON INSTANCE
# ===========================================


@lru_cache
def get_settings() -> Settings:
    """
    Obtiene la instancia singleton de settings.

    Uso:
        from src.config import settings

        print(settings.app_name)
        print(settings.database_url)
    """
    return Settings()


# Export singleton
settings = get_settings()


# ===========================================
# ENVIRONMENT-SPECIFIC CONFIGS
# ===========================================


class DevelopmentSettings(Settings):
    """Configuración para desarrollo."""

    environment: Literal["development"] = "development"
    debug: bool = True
    db_echo: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"


class ProductionSettings(Settings):
    """Configuración para producción."""

    environment: Literal["production"] = "production"
    debug: bool = False
    db_echo: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING"

    # Security: CORS más restrictivo
    cors_credentials: bool = True

    # Performance: cache más agresivo
    cache_ttl_default: int = 600
    cache_ttl_ai_response: int = 7200


class StagingSettings(Settings):
    """Configuración para staging."""

    environment: Literal["staging"] = "staging"
    debug: bool = False
    db_echo: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
