"""
C2Pro - FastAPI Application

Aplicación principal de la API de C2Pro.

Refers to Suite ID: TS-CORE-MCP-STARTUP-001.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.core.cache import close_cache, init_cache
from src.core.database import close_db, init_db
from src.core.events import build_event_bus
from src.core.handlers import register_exception_handlers
from src.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TenantIsolationMiddleware,
)
from src.core.mcp.servers.database_server import get_mcp_server

# Import core routers (always enabled)
from src.core.auth.router import router as auth_router
from src.documents.adapters.http.router import router as documents_router
from src.core.observability.router import router as observability_router
from src.projects.adapters.http.router import router as projects_router
from src.modules.decision_intelligence.adapters.http.router import (
    router as decision_intelligence_router,
)
from src.alerts.router import router as alerts_router
from src.bulk_operations.router import router as bulk_operations_router
from src.core.routers.health import router as health_router
from src.modules.hitl.adapters.http.router import router as hitl_router

logger = structlog.get_logger()


def _load_mcp_router():
    """Load the MCP router lazily so MCP is not a hard import-time dependency."""
    from src.core.mcp.router import router as mcp_router

    return mcp_router


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

    app.state.event_bus = build_event_bus(
        redis_url=settings.redis_url,
        environment=settings.environment,
    )
    logger.info("event_bus_initialized", adapter=type(app.state.event_bus).__name__)

    app.state.mcp_server = get_mcp_server()
    logger.info("mcp_server_initialized")

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

    if hasattr(app.state, "event_bus"):
        close_event_bus = getattr(app.state.event_bus, "close", None)
        if callable(close_event_bus):
            await close_event_bus()
            logger.info("event_bus_closed")

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

    api_v1_prefix = settings.api_v1_prefix

    # --- Core routers (always enabled) ---
    app.include_router(health_router)
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(projects_router, prefix=api_v1_prefix)
    app.include_router(documents_router, prefix=api_v1_prefix)
    app.include_router(alerts_router, prefix=api_v1_prefix)
    app.include_router(bulk_operations_router, prefix=api_v1_prefix)
    app.include_router(observability_router, prefix=api_v1_prefix)
    app.include_router(decision_intelligence_router, prefix=api_v1_prefix)
    app.include_router(hitl_router, prefix=api_v1_prefix)

    try:
        app.include_router(_load_mcp_router(), prefix=api_v1_prefix)
        logger.info("router_registered", feature="mcp")
    except ImportError:
        logger.warning("router_unavailable", feature="mcp", reason="module_not_ready")

    # --- Feature-gated routers ---
    _feature_flags = {
        "coherence_analysis": settings.feature_coherence_analysis,
        "stakeholder_extraction": settings.feature_stakeholder_extraction,
        "raci_generation": settings.feature_raci_generation,
        "rfq_generation": settings.feature_rfq_generation,
        "expediting_vision": settings.feature_expediting_vision,
    }

    logger.info("feature_flags", **_feature_flags)

    # Coherence Analysis (feature_coherence_analysis)
    if settings.feature_coherence_analysis:
        from src.coherence.router import (
            router as coherence_router,
            dashboard_router as coherence_dashboard_router,
        )
        app.include_router(coherence_router)
        app.include_router(coherence_dashboard_router)
        logger.info("router_registered", feature="coherence_analysis")
    else:
        logger.info("router_skipped", feature="coherence_analysis", reason="feature_flag_disabled")

    # Stakeholder Extraction (feature_stakeholder_extraction)
    if settings.feature_stakeholder_extraction:
        try:
            from src.stakeholders.adapters.http.router import router as stakeholders_router
            app.include_router(stakeholders_router, prefix=api_v1_prefix)
            logger.info("router_registered", feature="stakeholder_extraction")
        except ImportError:
            logger.warning("router_unavailable", feature="stakeholder_extraction", reason="module_not_ready")

        try:
            from src.stakeholders.adapters.http.approvals_router import router as approvals_router
            app.include_router(approvals_router, prefix=api_v1_prefix)
            logger.info("router_registered", feature="stakeholder_approvals")
        except ImportError:
            logger.warning("router_unavailable", feature="stakeholder_approvals", reason="module_not_ready")
    else:
        logger.info("router_skipped", feature="stakeholder_extraction", reason="feature_flag_disabled")

    # RACI Generation (feature_raci_generation)
    if settings.feature_raci_generation:
        try:
            from src.stakeholders.adapters.http.raci_router import router as raci_router
            app.include_router(raci_router, prefix=api_v1_prefix)
            logger.info("router_registered", feature="raci_generation")
        except ImportError:
            logger.warning("router_unavailable", feature="raci_generation", reason="module_not_ready")
    else:
        logger.info("router_skipped", feature="raci_generation", reason="feature_flag_disabled")

    # RFQ / Procurement (feature_rfq_generation)
    if settings.feature_rfq_generation:
        try:
            from src.procurement.adapters.http.router import router as procurement_router
            app.include_router(procurement_router, prefix=api_v1_prefix)
            logger.info("router_registered", feature="rfq_generation")
        except ImportError:
            logger.warning("router_unavailable", feature="rfq_generation", reason="module_not_ready")
    else:
        logger.info("router_skipped", feature="rfq_generation", reason="feature_flag_disabled")

    logger.info("application_configured", enabled_features=[k for k, v in _feature_flags.items() if v])

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
