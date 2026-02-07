"""
C2Pro - FastAPI Application

Aplicación principal de la API de C2Pro.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.core.cache import close_cache, init_cache
from src.core.database import close_db, init_db
from src.core.handlers import register_exception_handlers
from src.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TenantIsolationMiddleware,
)
from src.core.mcp.router import router as mcp_router

# Import routers
from src.core.auth.router import router as auth_router
from src.coherence.router import router as coherence_router
# from src.documents.adapters.http.router import router as documents_router  # TODO: GREEN phase - incomplete
from src.core.observability.router import router as observability_router
from src.projects.adapters.http.router import router as projects_router  # GREEN phase implementation
# from src.analysis.adapters.http.router import router as analysis_router  # TODO: GREEN phase - incomplete
# from src.analysis.adapters.http.alerts_router import router as alerts_router  # TODO: GREEN phase - incomplete
from src.core.routers.health import router as health_router
# from src.stakeholders.adapters.http.approvals_router import router as approvals_router  # TODO: GREEN phase - incomplete
# from src.stakeholders.adapters.http.raci_router import router as raci_router  # TODO: GREEN phase - incomplete
# from src.stakeholders.adapters.http.router import router as stakeholders_router  # TODO: GREEN phase - incomplete
# from src.procurement.adapters.http.router import router as procurement_router  # TODO: GREEN phase - incomplete

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

    await init_cache()
    logger.info("cache_initialized")

    # TODO: Inicializar Sentry cuando esté configurado

    logger.info("application_started")

    yield

    # SHUTDOWN
    logger.info("application_shutting_down")

    # Cerrar base de datos
    await close_db()
    logger.info("database_closed")

    await close_cache()
    logger.info("cache_closed")

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
        docs_url="/docs",
        redoc_url="/redoc",
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
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantIsolationMiddleware)

    # ===========================================
    # EXCEPTION HANDLERS
    # ===========================================

    # Registrar todos los exception handlers globales
    # Ver src/core/handlers.py para detalles de implementación
    register_exception_handlers(app)

    # ===========================================
    # ROUTERS
    # ===========================================

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

    app.include_router(health_router)

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

    # TODO: GREEN phase - Uncomment when modules are fully implemented
    # app.include_router(
    #     documents_router,
    #     prefix=api_v1_prefix,
    # )

    # app.include_router(
    #     analysis_router,
    #     prefix=api_v1_prefix,
    # )

    # app.include_router(
    #     alerts_router,
    #     prefix=api_v1_prefix,
    # )

    # app.include_router(
    #     approvals_router,
    #     prefix=api_v1_prefix,
    # )

    # app.include_router(
    #     stakeholders_router,
    #     prefix=api_v1_prefix,
    # )

    # app.include_router(
    #     raci_router,
    #     prefix=api_v1_prefix,
    # )

    # app.include_router(
    #     procurement_router,
    #     prefix=api_v1_prefix,
    # )

    # Coherence Engine v0 router (no v1 prefix)
    app.include_router(coherence_router)

    # TODO: Añadir más routers conforme se implementen
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
