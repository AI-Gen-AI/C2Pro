"""
C2Pro - Authentication Service

Lógica de negocio para autenticación y gestión de usuarios.
"""

from datetime import datetime, timedelta
from typing import Tuple
from uuid import UUID
import secrets
import string

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import settings
from src.core.exceptions import (
    AuthenticationError,
    ValidationError,
    NotFoundError,
    ConflictError,
)
from src.modules.auth.models import User, Tenant, UserRole, SubscriptionPlan
from src.modules.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    TenantResponse,
    LoginResponse,
    RegisterResponse,
    TokenPayload,
)

logger = structlog.get_logger()

# ===========================================
# PASSWORD HASHING
# ===========================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds
)


def hash_password(password: str) -> str:
    """
    Hash de contraseña usando bcrypt.

    Args:
        password: Contraseña en texto plano

    Returns:
        Hash de la contraseña
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica contraseña contra hash.

    Args:
        plain_password: Contraseña en texto plano
        hashed_password: Hash almacenado

    Returns:
        True si coincide, False si no
    """
    return pwd_context.verify(plain_password, hashed_password)


# ===========================================
# JWT TOKEN GENERATION
# ===========================================

def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    email: str,
    role: UserRole,
    expires_delta: timedelta | None = None
) -> str:
    """
    Crea JWT access token.

    Args:
        user_id: ID del usuario
        tenant_id: ID del tenant
        email: Email del usuario
        role: Rol del usuario
        expires_delta: Tiempo de expiración (opcional)

    Returns:
        Token JWT firmado
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "role": role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def create_refresh_token(user_id: UUID) -> str:
    """
    Crea JWT refresh token.

    Args:
        user_id: ID del usuario

    Returns:
        Token JWT firmado
    """
    expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)
    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_token(token: str) -> TokenPayload:
    """
    Decodifica y valida JWT token.

    Args:
        token: JWT token

    Returns:
        Payload decodificado

    Raises:
        AuthenticationError: Si el token es inválido
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        user_id = UUID(payload.get("sub"))
        tenant_id = UUID(payload.get("tenant_id"))
        email = payload.get("email")
        role = UserRole(payload.get("role"))
        exp = datetime.fromtimestamp(payload.get("exp"))
        iat = datetime.fromtimestamp(payload.get("iat"))

        return TokenPayload(
            sub=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            exp=exp,
            iat=iat
        )

    except JWTError as e:
        logger.warning("jwt_decode_error", error=str(e))
        raise AuthenticationError("Invalid token")
    except (KeyError, ValueError) as e:
        logger.warning("jwt_payload_error", error=str(e))
        raise AuthenticationError("Invalid token payload")


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def generate_tenant_slug(name: str) -> str:
    """
    Genera slug único para tenant desde el nombre.

    Args:
        name: Nombre del tenant

    Returns:
        Slug único (lowercase, sin espacios, alfanumérico + guiones)
    """
    # Convertir a lowercase y reemplazar espacios con guiones
    slug = name.lower().strip()
    slug = slug.replace(" ", "-")

    # Remover caracteres no alfanuméricos (excepto guiones)
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    # Remover guiones múltiples
    while "--" in slug:
        slug = slug.replace("--", "-")

    # Remover guiones al inicio/final
    slug = slug.strip("-")

    # Añadir random suffix para unicidad
    random_suffix = "".join(
        secrets.choice(string.ascii_lowercase + string.digits)
        for _ in range(6)
    )

    return f"{slug}-{random_suffix}"


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Obtiene usuario por email.

    Args:
        db: Sesión de base de datos
        email: Email del usuario

    Returns:
        Usuario si existe, None si no
    """
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """
    Obtiene usuario por ID.

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario

    Returns:
        Usuario si existe, None si no
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ===========================================
# AUTHENTICATION SERVICE
# ===========================================

class AuthService:
    """Servicio de autenticación."""

    @staticmethod
    async def register(
        db: AsyncSession,
        request: RegisterRequest
    ) -> RegisterResponse:
        """
        Registra nuevo usuario y crea tenant.

        Args:
            db: Sesión de base de datos
            request: Datos de registro

        Returns:
            Response con usuario, tenant y tokens

        Raises:
            ConflictError: Si el email ya existe
            ValidationError: Si los datos son inválidos
        """
        # Verificar que el email no exista
        existing_user = await get_user_by_email(db, request.email)
        if existing_user:
            logger.warning("registration_email_exists", email=request.email)
            raise ConflictError("Email already registered")

        try:
            # 1. Crear Tenant
            tenant_slug = generate_tenant_slug(request.company_name)

            tenant = Tenant(
                name=request.company_name,
                slug=tenant_slug,
                subscription_plan=SubscriptionPlan.FREE,
                subscription_status="active",
                subscription_started_at=datetime.utcnow(),
                ai_budget_monthly=settings.ai_budget_monthly_default,
                ai_spend_current=0.0,
                ai_spend_last_reset=datetime.utcnow(),
            )

            db.add(tenant)
            await db.flush()  # Para obtener el ID del tenant

            # 2. Crear Usuario (primer usuario es admin)
            hashed_pwd = hash_password(request.password)

            user = User(
                tenant_id=tenant.id,
                email=request.email,
                hashed_password=hashed_pwd,
                first_name=request.first_name,
                last_name=request.last_name,
                role=UserRole.ADMIN,  # Primer usuario es admin
                is_active=True,
                is_verified=False,  # Requerirá verificación de email
            )

            db.add(user)
            await db.commit()
            await db.refresh(user)
            await db.refresh(tenant)

            logger.info(
                "user_registered",
                user_id=str(user.id),
                tenant_id=str(tenant.id),
                email=user.email
            )

            # 3. Generar tokens
            access_token = create_access_token(
                user_id=user.id,
                tenant_id=tenant.id,
                email=user.email,
                role=user.role
            )

            refresh_token = create_refresh_token(user_id=user.id)

            tokens = TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.jwt_access_token_expire_minutes * 60,
                refresh_token=refresh_token
            )

            # 4. Actualizar last_login
            user.update_last_login()
            await db.commit()

            return RegisterResponse(
                user=UserResponse.model_validate(user),
                tenant=TenantResponse.model_validate(tenant),
                tokens=tokens,
                message="Registration successful. Please verify your email."
            )

        except Exception as e:
            await db.rollback()
            logger.error("registration_error", error=str(e))
            raise

    @staticmethod
    async def login(
        db: AsyncSession,
        request: LoginRequest
    ) -> LoginResponse:
        """
        Autentica usuario y retorna tokens.

        Args:
            db: Sesión de base de datos
            request: Credenciales de login

        Returns:
            Response con usuario, tenant y tokens

        Raises:
            AuthenticationError: Si las credenciales son inválidas
        """
        # 1. Buscar usuario por email
        user = await get_user_by_email(db, request.email)

        if not user:
            logger.warning("login_user_not_found", email=request.email)
            raise AuthenticationError("Invalid credentials")

        # 2. Verificar contraseña
        if not user.hashed_password:
            logger.warning("login_no_password", user_id=str(user.id))
            raise AuthenticationError("Invalid credentials")

        if not verify_password(request.password, user.hashed_password):
            logger.warning("login_invalid_password", user_id=str(user.id))
            raise AuthenticationError("Invalid credentials")

        # 3. Verificar que el usuario esté activo
        if not user.is_active:
            logger.warning("login_inactive_user", user_id=str(user.id))
            raise AuthenticationError("Account is inactive")

        # 4. Verificar que el tenant esté activo
        if not user.tenant.is_active:
            logger.warning("login_inactive_tenant", tenant_id=str(user.tenant_id))
            raise AuthenticationError("Organization account is inactive")

        # 5. Generar tokens
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=user.role
        )

        refresh_token = create_refresh_token(user_id=user.id)

        tokens = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            refresh_token=refresh_token
        )

        # 6. Actualizar last_login
        user.update_last_login()
        await db.commit()

        logger.info("user_logged_in", user_id=str(user.id), email=user.email)

        return LoginResponse(
            user=UserResponse.model_validate(user),
            tenant=TenantResponse.model_validate(user.tenant),
            tokens=tokens
        )

    @staticmethod
    async def get_current_user(
        db: AsyncSession,
        user_id: UUID
    ) -> User:
        """
        Obtiene usuario actual por ID.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario

        Returns:
            Usuario

        Raises:
            NotFoundError: Si el usuario no existe
        """
        user = await get_user_by_id(db, user_id)

        if not user:
            raise NotFoundError("User not found")

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        # Actualizar última actividad
        user.update_last_activity()
        await db.commit()

        return user

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token: str
    ) -> TokenResponse:
        """
        Refresca access token usando refresh token.

        Args:
            db: Sesión de base de datos
            refresh_token: Refresh token JWT

        Returns:
            Nuevos tokens

        Raises:
            AuthenticationError: Si el token es inválido
        """
        try:
            # Decodificar refresh token
            payload = jwt.decode(
                refresh_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )

            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")

            user_id = UUID(payload.get("sub"))

            # Obtener usuario
            user = await get_user_by_id(db, user_id)

            if not user or not user.is_active:
                raise AuthenticationError("Invalid token")

            # Generar nuevo access token
            access_token = create_access_token(
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role
            )

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.jwt_access_token_expire_minutes * 60
            )

        except JWTError as e:
            logger.warning("refresh_token_error", error=str(e))
            raise AuthenticationError("Invalid refresh token")
