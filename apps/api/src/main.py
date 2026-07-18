"""
C2Pro - FastAPI Application

AplicaciÃ³n principal de la API de C2Pro.

Refers to Suite ID: TS-CORE-MCP-STARTUP-001.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.utils import BadDsn

# Import AI tools to trigger registration via @register_tool decorators
import src.analysis.adapters.ai.tools  # noqa: F401
from src.admin.adapters.http.router import router as dlq_admin_router
from src.ai_feedback.router import router as ai_feedback_router
from src.alerts.adapters.http.router import project_alerts_router
from src.alerts.adapters.http.router import router as alerts_router
from src.analysis.adapters.graph.workflow import (
    close_checkpointer_resources,
    ensure_checkpointer_ready,
)
from src.analysis.adapters.http.router import router as analysis_router  # LangGraph orchestration
from src.bulk_operations.router import router as bulk_operations_router
from src.config import settings
from src.core.ai.analytics_router import router as ai_analytics_router

# Import core routers (always enabled)
from src.core.auth.router import router as auth_router
from src.core.cache import close_cache, init_cache
from src.core.database import close_db, init_db
from src.core.events import build_event_bus
from src.core.frontend_support.router import router as frontend_support_router
from src.core.handlers import register_exception_handlers
from src.core.mcp.servers.database_server import get_mcp_server
from src.core.middleware import (
    APIContractMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TenantIsolationMiddleware,
)
from src.core.observability.router import router as observability_router
from src.core.routers.health import router as health_router
from src.core.routers.health import worker_health_check
from src.documents.adapters.http.router import router as documents_router
from src.health.adapters.http.router import router as project_health_router
from src.modules.decision_intelligence.adapters.http.router import (
    router as decision_intelligence_router,
)
from src.modules.decision_intelligence.runtime import (
    build_decision_intelligence_services,
)
from src.modules.hitl.adapters.http.notification_settings_router import (
    router as notification_settings_router,  # TASK-BCK-025
)
from src.modules.hitl.adapters.http.router import router as hitl_router
from src.projects.adapters.http.router import router as projects_router
from src.wbs.adapters.http.router import router as wbs_router  # GREEN phase - TS-CT-WBS-API-001

logger = structlog.get_logger()


def _load_mcp_router() -> APIRouter:
    """Load the MCP router lazily so MCP is not a hard import-time dependency."""
    from src.core.mcp.router import router as mcp_router

    return mcp_router


# ===========================================
# LIFESPAN CONTEXT MANAGER
# ===========================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager para startup/shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None durante la ejecuciÃ³n de la aplicaciÃ³n
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

    await ensure_checkpointer_ready()
    logger.info("langgraph_checkpointer_initialized")

    # Refers to Suite ID: TS-I13-E2E-REAL-001.
    # Wire real Decision Intelligence port adapters into app.state so the
    # HTTP router can satisfy get_ingestion_service/get_extraction_service/
    # get_retrieval_service/get_coherence_scoring_service/get_hitl_service
    # dependencies without falling back to the 503 "requires real port
    # implementations" fail-closed path.
    try:
        di_services = build_decision_intelligence_services()
    except Exception as exc:
        logger.error(
            "decision_intelligence_services_init_failed",
            error=str(exc),
        )
    else:
        app.state.decision_ingestion_service = di_services.ingestion
        app.state.decision_extraction_service = di_services.extraction
        app.state.decision_retrieval_service = di_services.retrieval
        app.state.decision_coherence_scoring_service = di_services.coherence
        app.state.decision_hitl_service = di_services.hitl
        logger.info("decision_intelligence_services_initialized")

    sentry_enabled = bool(settings.sentry_dsn)
    app.state.sentry_enabled = sentry_enabled
    if sentry_enabled:
        try:
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.sentry_environment or settings.environment,
                traces_sample_rate=settings.sentry_traces_sample_rate,
            )
            logger.info("sentry_initialized")
        except BadDsn:
            app.state.sentry_enabled = False
            logger.warning(
                "sentry_initialization_skipped",
                reason="invalid_dsn",
            )

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

    if getattr(app.state, "sentry_enabled", False):
        sentry_sdk.flush()
        logger.info("sentry_flushed")

    await close_checkpointer_resources()
    logger.info("langgraph_checkpointer_closed")

    logger.info("application_stopped")


# ===========================================
# CREATE APPLICATION
# ===========================================


def create_application() -> FastAPI:
    """
    Factory para crear la aplicaciÃ³n FastAPI.

    Returns:
        FastAPI application instance configurada
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        **C2Pro - Contract Intelligence Platform**

        Plataforma de inteligencia contractual para proyectos de construcciÃ³n e ingenierÃ­a.

        ## CaracterÃ­sticas

        - ðŸ” **AuditorÃ­a Tridimensional**: Detecta incoherencias entre contrato, cronograma y presupuesto
        - ðŸ¤– **IA Especializada**: Claude 4 entrenado en documentos de construcciÃ³n
        - ðŸ“Š **Coherence Score**: Indicador 0-100 de alineaciÃ³n entre documentos
        - ðŸ‘¥ **Stakeholder Intelligence**: ExtracciÃ³n y mapeo automÃ¡tico de stakeholders
        - ðŸ“ˆ **Multi-tenant**: Aislamiento completo de datos por organizaciÃ³n

        ## AutenticaciÃ³n

        La API usa JWT (JSON Web Tokens) para autenticaciÃ³n.

        1. **Registro**: `POST /api/v1/auth/register`
        2. **Login**: `POST /api/v1/auth/login`
        3. **Usar Token**: Incluir en header `Authorization: Bearer <token>`

        ## LÃ­mites de Uso

        - **Rate Limit**: 60 requests/minuto
        - **AI Budget**: $50 USD/mes (plan free)
        - **File Upload**: Max 50 MB

        ## Soporte

        - ðŸ“§ Email: support@c2pro.app
        - ðŸ“– Docs: https://docs.c2pro.app
        - ðŸ’¬ Discord: https://discord.gg/c2pro
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

    # Custom middleware
    app.add_middleware(APIContractMiddleware)  # Adds X-API-Version and X-Response-Time headers
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantIsolationMiddleware)

    # CORS must wrap auth/tenant middleware so even early 401/500 responses keep CORS headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # ===========================================
    # EXCEPTION HANDLERS
    # ===========================================

    # Registrar todos los exception handlers globales
    # Ver src/core/handlers.py para detalles de implementaciÃ³n
    register_exception_handlers(app)

    # ===========================================
    # ROUTERS
    # ===========================================

    # Root
    @app.get("/", tags=["Public"])
    async def root() -> dict[str, str]:
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

    app.add_api_route(
        f"{api_v1_prefix}/health/worker",
        worker_health_check,
        methods=["GET"],
        tags=["Health"],
        summary="Celery Worker Health",
    )

    # --- Core routers (always enabled) ---
    app.include_router(health_router)  # raw: /health/... (docker-compose, infra probes)
    app.include_router(health_router, prefix=api_v1_prefix)  # prefixed: /api/v1/health/... (gateway, deploy workflow)
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(projects_router, prefix=api_v1_prefix)
    app.include_router(project_health_router, prefix=api_v1_prefix)
    app.include_router(documents_router, prefix=api_v1_prefix)
    app.include_router(alerts_router, prefix=api_v1_prefix)
    app.include_router(project_alerts_router, prefix=api_v1_prefix)
    # COMPATIBILITY: Register project alerts without v1 prefix for legacy frontend calls
    app.include_router(project_alerts_router, prefix="/api")

    app.include_router(bulk_operations_router, prefix=api_v1_prefix)
    app.include_router(observability_router, prefix=api_v1_prefix)
    app.include_router(ai_feedback_router, prefix=api_v1_prefix)
    app.include_router(ai_analytics_router, prefix=api_v1_prefix)
    app.include_router(dlq_admin_router, prefix=api_v1_prefix)
    app.include_router(frontend_support_router, prefix=api_v1_prefix)
    app.include_router(decision_intelligence_router, prefix=api_v1_prefix)
    app.include_router(hitl_router, prefix=api_v1_prefix)
    app.include_router(notification_settings_router, prefix=api_v1_prefix)  # TASK-BCK-025
    app.include_router(wbs_router, prefix=api_v1_prefix)
    app.include_router(analysis_router, prefix=api_v1_prefix)  # LangGraph orchestration

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
            dashboard_router as coherence_dashboard_router,
        )
        from src.coherence.router import (
            router as coherence_router,
        )
        app.include_router(coherence_router, prefix=api_v1_prefix)
        app.include_router(coherence_dashboard_router, prefix=api_v1_prefix)
        # COMPATIBILITY: Register dashboard without v1 prefix
        app.include_router(coherence_dashboard_router, prefix="/api")
        logger.info("router_registered", feature="coherence_analysis")
    else:
        logger.info("router_skipped", feature="coherence_analysis", reason="feature_flag_disabled")

    # Stakeholder Extraction (feature_stakeholder_extraction)
    if settings.feature_stakeholder_extraction:
        try:
            from src.stakeholders.adapters.http.router import router as stakeholders_router
            app.include_router(stakeholders_router, prefix=api_v1_prefix)
            # COMPATIBILITY: Register stakeholders without v1 prefix
            app.include_router(stakeholders_router, prefix="/api")
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
            from src.stakeholders.adapters.http.raci_router import (
                raci_global_router,
            )
            from src.stakeholders.adapters.http.raci_router import (
                router as raci_router,
            )
            app.include_router(raci_global_router, prefix=api_v1_prefix)
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
