"""
C2Pro - FastAPI Application

Aplicación principal de la API de C2Pro.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.core.database import close_db, init_db
from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    TenantNotFoundError,
    ValidationError,
)
from src.core.middleware import (
    RequestLoggingMiddleware,
    TenantIsolationMiddleware,
)
from src.mcp.router import router as mcp_router

# Import routers
from src.modules.auth.router import router as auth_router
from src.modules.coherence.router import router as coherence_router
from src.modules.documents.router import router as documents_router
from src.modules.observability.router import router as observability_router
from src.modules.projects.router import router as projects_router

logger = structlog.get_logger()


# ===========================================
# LIFESPAN CONTEXT MANAGER
# ===========================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager para startup/shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None durante la ejecución de la aplicación
    """
    # STARTUP
    logger.info("application_starting", environment=settings.environment, debug=settings.debug)

    # Inicializar base de datos
    await init_db()
    logger.info("database_initialized")

    # TODO: Inicializar Redis/cache cuando esté implementado
    # TODO: Inicializar Sentry cuando esté configurado

    logger.info("application_started")

    yield

    # SHUTDOWN
    logger.info("application_shutting_down")

    # Cerrar base de datos
    await close_db()
    logger.info("database_closed")

    # TODO: Cerrar conexiones Redis
    # TODO: Flush Sentry events

    logger.info("application_stopped")


# ===========================================
# CREATE APPLICATION
# ===========================================


def create_application() -> FastAPI:
    """
    Factory para crear la aplicación FastAPI.

    Returns:
        FastAPI application instance configurada
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        **C2Pro - Contract Intelligence Platform**

        Plataforma de inteligencia contractual para proyectos de construcción e ingeniería.

        ## Características

        - 🔍 **Auditoría Tridimensional**: Detecta incoherencias entre contrato, cronograma y presupuesto
        - 🤖 **IA Especializada**: Claude 4 entrenado en documentos de construcción
        - 📊 **Coherence Score**: Indicador 0-100 de alineación entre documentos
        - 👥 **Stakeholder Intelligence**: Extracción y mapeo automático de stakeholders
        - 📈 **Multi-tenant**: Aislamiento completo de datos por organización

        ## Autenticación

        La API usa JWT (JSON Web Tokens) para autenticación.

        1. **Registro**: `POST /api/v1/auth/register`
        2. **Login**: `POST /api/v1/auth/login`
        3. **Usar Token**: Incluir en header `Authorization: Bearer <token>`

        ## Límites de Uso

        - **Rate Limit**: 60 requests/minuto
        - **AI Budget**: $50 USD/mes (plan free)
        - **File Upload**: Max 50 MB

        ## Soporte

        - 📧 Email: support@c2pro.app
        - 📖 Docs: https://docs.c2pro.app
        - 💬 Discord: https://discord.gg/c2pro
        """,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
        debug=settings.debug,
        redirect_slashes=False,  # Disable automatic slash redirects for security tests
    )

    # ===========================================
    # MIDDLEWARE
    # ===========================================

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantIsolationMiddleware)

    # ===========================================
    # EXCEPTION HANDLERS
    # ===========================================

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError):
        """Handler para errores de autenticación."""
        logger.warning("authentication_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(TenantNotFoundError)
    async def tenant_not_found_handler(request: Request, exc: TenantNotFoundError):
        """Handler para tenant no encontrado."""
        logger.warning("tenant_not_found", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid authentication context"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(request: Request, exc: NotFoundError):
        """Handler para recursos no encontrados."""
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(request: Request, exc: ConflictError):
        """Handler para conflictos (duplicados, etc)."""
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Handler para errores de validación de negocio."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)}
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        """Handler para errores de validación de Pydantic."""
        logger.warning("validation_error", path=request.url.path, errors=exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handler para errores no capturados."""
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error" if settings.is_production else str(exc)},
        )

    # ===========================================
    # ROUTERS
    # ===========================================

    # Health check
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint.

        Returns basic application status and version.
        """
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    # Root
    @app.get("/", tags=["Root"])
    async def root():
        """
        Root endpoint.

        Redirects to API documentation.
        """
        return {
            "message": f"Welcome to {settings.app_name} API",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
        }

    # API v1 routers
    api_v1_prefix = settings.api_v1_prefix

    app.include_router(
        auth_router,
        prefix=api_v1_prefix,
    )

    app.include_router(
        projects_router,
        prefix=api_v1_prefix,
    )

    app.include_router(
        mcp_router,
        prefix=api_v1_prefix,
    )

    app.include_router(
        observability_router,
        prefix=api_v1_prefix,
    )

    app.include_router(
        documents_router,
        prefix=api_v1_prefix,
    )

    # Coherence Engine v0 router (no v1 prefix)
    app.include_router(coherence_router)

    # TODO: Añadir más routers conforme se implementen
    # app.include_router(analysis_router, prefix=api_v1_prefix)
    # app.include_router(stakeholders_router, prefix=api_v1_prefix)

    logger.info("application_configured")

    return app


# ===========================================
# APPLICATION INSTANCE
# ===========================================

app = create_application()


# ===========================================
# DEVELOPMENT SERVER
# ===========================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
