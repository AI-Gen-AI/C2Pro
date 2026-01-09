"""
C2Pro - Authentication Router

Endpoints de autenticación y gestión de usuarios.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from src.core.security import CurrentUserId
from src.modules.auth.schemas import (
    AuthErrorResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    PasswordChangeRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TenantResponse,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from src.modules.auth.service import AuthService

logger = structlog.get_logger()

# ===========================================
# ROUTER SETUP
# ===========================================

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={
        401: {
            "description": "Unauthorized - Invalid or missing credentials",
            "model": AuthErrorResponse,
        },
        403: {"description": "Forbidden - Insufficient permissions", "model": AuthErrorResponse},
    },
)

# ===========================================
# PUBLIC ENDPOINTS (sin autenticación)
# ===========================================


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user and company",
    description="""
    Registers a new user and creates a new company (tenant).

    The first user registered for a company becomes the admin.
    Returns user info, company info, and authentication tokens.

    **Requirements:**
    - Email must be unique
    - Password must be at least 8 characters with uppercase, lowercase, and digit
    - Must accept terms and conditions
    """,
    responses={
        201: {"description": "User successfully registered"},
        409: {"description": "Email already exists"},
        422: {"description": "Validation error"},
    },
)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_session)):
    """
    Registra nuevo usuario y crea empresa/organización (tenant).

    El primer usuario registrado se convierte en administrador del tenant.
    """
    try:
        response = await AuthService.register(db, request)

        logger.info("user_registered_via_api", email=request.email, company=request.company_name)

        return response

    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error("registration_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login with email and password",
    description="""
    Authenticates a user with email and password.

    Returns user info, company info, and JWT tokens.

    **Tokens:**
    - `access_token`: Use for API requests (expires in 24h)
    - `refresh_token`: Use to get new access token (expires in 30 days)
    """,
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        422: {"description": "Validation error"},
    },
)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_session)):
    """
    Autentica usuario con email y contraseña.

    Retorna información del usuario, empresa y tokens JWT.
    """
    try:
        response = await AuthService.login(db, request)

        logger.info("user_logged_in_via_api", email=request.email)

        return response

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error("login_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="""
    Refreshes the access token using a valid refresh token.

    Use this endpoint when your access token expires to get a new one
    without requiring the user to log in again.
    """,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_session)):
    """
    Refresca el access token usando el refresh token.
    """
    try:
        response = await AuthService.refresh_access_token(db, request.refresh_token)

        logger.info("token_refreshed")

        return response

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ===========================================
# PROTECTED ENDPOINTS (requieren autenticación)
# ===========================================


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current user info",
    description="""
    Returns information about the currently authenticated user.

    Requires valid JWT access token in Authorization header:
    ```
    Authorization: Bearer <access_token>
    ```
    """,
    responses={
        200: {"description": "User info retrieved successfully"},
        401: {"description": "Not authenticated or invalid token"},
    },
)
async def get_me(user_id: CurrentUserId, db: AsyncSession = Depends(get_session)):
    """
    Obtiene información del usuario actual autenticado.
    """
    try:
        user = await AuthService.get_current_user(db, user_id)

        return MeResponse(
            user=UserResponse.model_validate(user),
            tenant=TenantResponse.model_validate(user.tenant),
        )

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
    description="""
    Updates the profile of the currently authenticated user.

    Only the user can update their own profile.
    """,
)
async def update_me(
    request: UserUpdateRequest, user_id: CurrentUserId, db: AsyncSession = Depends(get_session)
):
    """
    Actualiza el perfil del usuario actual.
    """
    try:
        user = await AuthService.get_current_user(db, user_id)

        # Actualizar campos si se proporcionan
        if request.first_name is not None:
            user.first_name = request.first_name

        if request.last_name is not None:
            user.last_name = request.last_name

        if request.phone is not None:
            user.phone = request.phone

        if request.avatar_url is not None:
            user.avatar_url = request.avatar_url

        if request.preferences is not None:
            user.preferences = request.preferences

        await db.commit()
        await db.refresh(user)

        logger.info("user_profile_updated", user_id=str(user_id))

        return UserResponse.model_validate(user)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout current user",
    description="""
    Logs out the current user.

    Note: With JWT tokens, actual logout is handled client-side by
    removing the tokens. This endpoint is for logging purposes.
    """,
)
async def logout(user_id: CurrentUserId):
    """
    Cierra sesión del usuario actual.

    Nota: Con JWT, el logout real se maneja en el cliente eliminando los tokens.
    Este endpoint es principalmente para logging/auditoría.
    """
    logger.info("user_logged_out", user_id=str(user_id))
    return None


# ===========================================
# PASSWORD MANAGEMENT
# ===========================================


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="""
    Changes the password for the currently authenticated user.

    Requires:
    - Current password (for verification)
    - New password (must meet security requirements)
    """,
)
async def change_password(
    request: PasswordChangeRequest, user_id: CurrentUserId, db: AsyncSession = Depends(get_session)
):
    """
    Cambia la contraseña del usuario actual.
    """
    from src.modules.auth.service import hash_password, verify_password

    try:
        user = await AuthService.get_current_user(db, user_id)

        # Verificar contraseña actual
        if not user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change password for OAuth users",
            )

        if not verify_password(request.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect"
            )

        # Actualizar contraseña
        user.hashed_password = hash_password(request.new_password)
        await db.commit()

        logger.info("password_changed", user_id=str(user_id))

        return None

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ===========================================
# HEALTH CHECK
# ===========================================


@router.get(
    "/health",
    summary="Health check",
    description="Simple health check endpoint for authentication service",
    include_in_schema=False,
)
async def health():
    """Health check para el servicio de autenticación."""
    return {"status": "ok", "service": "auth"}
