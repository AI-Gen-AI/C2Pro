"""
C2Pro API - Main Application

Entry point de la aplicación FastAPI.
"""

# LEGACY: prefer `src/main.py` for runtime. This file is kept for historical reference.

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from src.config import settings
from src.core.database import close_db, init_db
from src.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TenantIsolationMiddleware,
)
from src.core.observability import configure_logging, init_sentry
from src.analysis.adapters.http.router import router as analysis_router
from src.core.auth.router import router as auth_router
from src.documents.adapters.http.router import router as documents_router
from src.modules.projects.router import router as projects_router

# Configure structured logging
configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle manager para startup y shutdown.
    """
    # Startup
    logger.info(
        "application_starting",
        environment=settings.environment,
        debug=settings.debug,
    )

    # Initialize Sentry
    if settings.sentry_dsn:
        init_sentry(settings.sentry_dsn, settings.environment)
        logger.info("sentry_initialized")

    # Initialize database
    await init_db()
    logger.info("database_initialized")

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await close_db()
    logger.info("database_closed")


def create_app() -> FastAPI:
    """
    Factory function para crear la aplicación FastAPI.
    """
    app = FastAPI(
        title="C2Pro API",
        description="Contract Intelligence & Procurement Optimization Platform",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # ===========================================
    # MIDDLEWARE (orden importa: último añadido = primero ejecutado)
    # ===========================================

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate Limiting
    app.add_middleware(RateLimitMiddleware)

    # Request Logging
    app.add_middleware(RequestLoggingMiddleware)

    # Tenant Isolation (crítico para seguridad)
    app.add_middleware(TenantIsolationMiddleware)

    # ===========================================
    # ROUTERS
    # ===========================================

    # Health checks (sin prefix, sin auth)
    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"])
    async def ready() -> dict:
        """Readiness probe."""
        # TODO: Verificar DB, Redis, etc.
        return {"status": "ready"}

    # API routes
    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    app.include_router(projects_router, prefix="/api/projects", tags=["Projects"])
    app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
    app.include_router(analysis_router, prefix="/api/analysis", tags=["Analysis"])

    # ===========================================
    # EXCEPTION HANDLERS
    # ===========================================

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
        """Captura excepciones no manejadas."""
        logger.error(
            "unhandled_exception",
            error=str(exc),
            path=request.url.path,
            method=request.method,
            exc_info=exc,
        )

        # Report to Sentry
        if settings.sentry_dsn:
            sentry_sdk.capture_exception(exc)

        # Don't expose internal errors in production
        if settings.is_production:
            return ORJSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        return ORJSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=settings.api_workers,
    )
