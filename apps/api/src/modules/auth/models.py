"""
C2Pro - Authentication Models

Modelos SQLAlchemy para usuarios y tenants (multi-tenancy).
"""

import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    event,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.projects.models import Project


class SubscriptionPlan(str, Enum):
    """Planes de suscripción disponibles."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class UserRole(str, Enum):
    """Roles de usuario."""

    ADMIN = "admin"  # Administrador del tenant
    USER = "user"  # Usuario estándar
    VIEWER = "viewer"  # Solo lectura
    API = "api"  # Usuario para integraciones API


class Tenant(Base):
    """
    Modelo de Tenant (empresa/organización).

    Proporciona aislamiento multi-tenant para todos los datos.
    Cada tenant tiene su propia suscripción y límites de uso.
    """

    __tablename__ = "tenants"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Subscription
    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(SubscriptionPlan, values_callable=lambda obj: [e.value for e in obj]),
        default=SubscriptionPlan.FREE,
    )
    subscription_status: Mapped[str] = mapped_column(
        String(50),
        default="active",  # active, suspended, cancelled
    )
    subscription_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # AI Budget Control
    ai_budget_monthly: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    ai_spend_current: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_spend_last_reset: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Usage limits (basados en plan)
    max_projects: Mapped[int] = mapped_column(default=5, nullable=False)
    max_users: Mapped[int] = mapped_column(default=3, nullable=False)
    max_storage_gb: Mapped[int] = mapped_column(default=10, nullable=False)

    # Settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", lazy="selectin", cascade="all, delete-orphan"
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project", foreign_keys="Project.tenant_id", lazy="select", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_tenants_subscription", "subscription_plan", "subscription_status"),
        Index("ix_tenants_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}', plan={self.subscription_plan.value})>"

    @property
    def is_over_budget(self) -> bool:
        """Verifica si ha excedido el presupuesto de AI."""
        return self.ai_spend_current >= self.ai_budget_monthly

    @property
    def budget_usage_percentage(self) -> float:
        """Porcentaje de presupuesto de AI usado."""
        if self.ai_budget_monthly <= 0:
            return 100.0
        return (self.ai_spend_current / self.ai_budget_monthly) * 100

    @property
    def user_count(self) -> int:
        """Número de usuarios activos."""
        return len([u for u in self.users if u.is_active])

    @property
    def is_at_user_limit(self) -> bool:
        """Verifica si ha alcanzado el límite de usuarios."""
        return self.user_count >= self.max_users


class User(Base):
    """
    Modelo de Usuario.

    Cada usuario pertenece a un tenant y tiene un rol específico.
    La autenticación puede ser manejada por Supabase o localmente.
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Tenant relationship (CRÍTICO para multi-tenancy)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Authentication
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # Nullable si usa OAuth
    )

    # OAuth (opcional - para integración futura)
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,  # google, github, etc.
    )
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Profile
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Role & Permissions
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, values_callable=lambda obj: [e.value for e in obj]), default=UserRole.USER
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Activity tracking
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    login_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Preferences
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users", lazy="selectin")

    # Indexes
    __table_args__ = (
        # Index compuesto para queries por tenant
        Index("ix_users_tenant_email", "tenant_id", "email"),
        Index("ix_users_tenant_role", "tenant_id", "role"),
        Index("ix_users_last_login", "last_login"),
        # RLS policy info (para documentación)
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', tenant={self.tenant_id})>"

    @property
    def full_name(self) -> str:
        """Nombre completo del usuario."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email.split("@")[0]

    @property
    def is_admin(self) -> bool:
        """Verifica si es administrador."""
        return self.role == UserRole.ADMIN

    @property
    def is_viewer(self) -> bool:
        """Verifica si es solo lectura."""
        return self.role == UserRole.VIEWER

    @property
    def can_edit(self) -> bool:
        """Verifica si puede editar."""
        return self.role in (UserRole.ADMIN, UserRole.USER)

    @property
    def can_manage_users(self) -> bool:
        """Verifica si puede gestionar usuarios."""
        return self.role == UserRole.ADMIN

    def update_last_login(self) -> None:
        """Actualiza el timestamp de último login."""
        self.last_login = datetime.utcnow()
        self.login_count += 1

    def update_last_activity(self) -> None:
        """Actualiza el timestamp de última actividad."""
        self.last_activity = datetime.utcnow()


# Event listeners
def _generate_slug_from_name(name: str) -> str:
    """
    Genera un slug válido a partir de un nombre.

    - Convierte a minúsculas
    - Reemplaza espacios y caracteres especiales con guiones
    - Elimina guiones múltiples
    """
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


@event.listens_for(Tenant, "before_insert")
def generate_tenant_slug(mapper, connection, target):
    """Auto-genera el slug si no se proporciona."""
    if not target.slug:
        target.slug = _generate_slug_from_name(target.name)
