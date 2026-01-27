"""
C2Pro - Authentication Schemas

Schemas Pydantic para validación y serialización de autenticación.
"""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from src.core.auth.models import SubscriptionPlan, UserRole

# ===========================================
# BASE SCHEMAS
# ===========================================


class TenantBase(BaseModel):
    """Schema base para Tenant."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class UserBase(BaseModel):
    """Schema base para User."""

    email: EmailStr
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)


# ===========================================
# REQUEST SCHEMAS (Input)
# ===========================================


class RegisterRequest(BaseModel):
    """Request para registro de nuevo usuario."""

    # Tenant info (si está creando nuevo tenant)
    company_name: str = Field(..., min_length=1, max_length=255)

    # User info
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    password_confirm: str | None = Field(
        None,
        min_length=8,
        max_length=100,
        description="Opcional; si se envía debe coincidir con password",
    )
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)

    # Terms acceptance
    accept_terms: bool = Field(..., description="Debe aceptar términos y condiciones")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_name": "Constructora Ejemplo S.L.",
                "email": "usuario@ejemplo.com",
                "password": "Password123!",
                "password_confirm": "Password123!",
                "first_name": "Juan",
                "last_name": "Pérez",
                "accept_terms": True,
            }
        }
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida que la contraseña sea segura."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")

        return v

    @field_validator("password_confirm")
    @classmethod
    def validate_passwords_match(cls, v: str | None, info) -> str | None:
        """Valida coincidencia solo si se envía confirmación."""
        if v is None:
            return v
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("accept_terms")
    @classmethod
    def validate_terms_accepted(cls, v: bool) -> bool:
        """Valida que se hayan aceptado los términos."""
        if not v:
            raise ValueError("You must accept the terms and conditions")
        return v


class LoginRequest(BaseModel):
    """Request para login."""

    email: EmailStr
    password: str = Field(..., min_length=1)

    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "usuario@ejemplo.com", "password": "Password123!"}}
    )


class PasswordChangeRequest(BaseModel):
    """Request para cambio de contraseña."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    new_password_confirm: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida que la contraseña sea segura."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")

        return v

    @field_validator("new_password_confirm")
    @classmethod
    def validate_passwords_match(cls, v: str, info) -> str:
        """Valida que las contraseñas coincidan."""
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class PasswordResetRequest(BaseModel):
    """Request para solicitar reset de contraseña."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Request para confirmar reset de contraseña."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    new_password_confirm: str = Field(..., min_length=8, max_length=100)


# ===========================================
# RESPONSE SCHEMAS (Output)
# ===========================================


class TenantResponse(BaseModel):
    """Response con información de Tenant."""

    id: UUID
    name: str
    slug: str
    subscription_plan: SubscriptionPlan
    subscription_status: str

    # AI Budget
    ai_budget_monthly: float
    ai_spend_current: float
    budget_usage_percentage: float
    is_over_budget: bool

    # Limits
    max_projects: int
    max_users: int
    max_storage_gb: int

    # Status
    is_active: bool
    user_count: int
    is_at_user_limit: bool

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Response con información de Usuario."""

    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    full_name: str
    avatar_url: str | None
    phone: str | None

    # Role & Status
    role: UserRole
    is_active: bool
    is_verified: bool

    # Permissions
    is_admin: bool
    is_viewer: bool
    can_edit: bool
    can_manage_users: bool

    # Activity
    last_login: datetime | None
    last_activity: datetime | None
    login_count: int

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Response con tokens de autenticación."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos
    refresh_token: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class LoginResponse(BaseModel):
    """Response completo de login."""

    user: UserResponse
    tenant: TenantResponse
    tokens: TokenResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "usuario@ejemplo.com",
                    "first_name": "Juan",
                    "last_name": "Pérez",
                    "role": "admin",
                },
                "tenant": {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "name": "Constructora Ejemplo S.L.",
                    "subscription_plan": "free",
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 86400,
                },
            }
        }
    )


class RegisterResponse(BaseModel):
    """Response completo de registro."""

    user: UserResponse
    tenant: TenantResponse
    tokens: TokenResponse
    message: str = "Registration successful. Please verify your email."


class RefreshTokenRequest(BaseModel):
    """Request para refrescar token."""

    refresh_token: str


class MeResponse(BaseModel):
    """Response para endpoint /me."""

    user: UserResponse
    tenant: TenantResponse


# ===========================================
# UPDATE SCHEMAS
# ===========================================


class UserUpdateRequest(BaseModel):
    """Request para actualizar perfil de usuario."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)
    preferences: dict | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"first_name": "Juan", "last_name": "Pérez", "phone": "+34 600 000 000"}
        }
    )


class TenantUpdateRequest(BaseModel):
    """Request para actualizar tenant (solo admin)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    settings: dict | None = None


# ===========================================
# JWT PAYLOAD SCHEMAS
# ===========================================


class TokenPayload(BaseModel):
    """Payload decodificado del JWT."""

    sub: UUID  # user_id
    tenant_id: UUID
    email: str
    role: UserRole
    exp: datetime
    iat: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# ERROR SCHEMAS
# ===========================================


class AuthErrorResponse(BaseModel):
    """Response de error de autenticación."""

    detail: str
    error_code: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"detail": "Invalid credentials", "error_code": "INVALID_CREDENTIALS"}
        }
    )
