"""
C2Pro - Database Configuration

SQLAlchemy async setup con Supabase PostgreSQL.
Incluye Row Level Security (RLS) para multi-tenancy.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
import structlog

from src.config import settings

logger = structlog.get_logger()


class Base(DeclarativeBase):
    """Base class para todos los modelos SQLAlchemy."""
    pass


# Engine global
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Inicializa conexión a la base de datos.
    Llamar en startup de la aplicación.
    """
    global _engine, _session_factory
    
    # Convertir URL a async
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    _engine = create_async_engine(
        database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    logger.info("database_engine_created", url=database_url[:50] + "...")


async def close_db() -> None:
    """
    Cierra conexión a la base de datos.
    Llamar en shutdown de la aplicación.
    """
    global _engine
    
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("database_engine_closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obtener sesión de base de datos.
    
    Uso en FastAPI:
        async def endpoint(db: AsyncSession = Depends(get_session)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session_with_tenant(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Obtiene sesión con RLS configurado para un tenant específico.
    
    IMPORTANTE: Usar esto para operaciones que requieren aislamiento de tenant.
    
    Uso:
        async with get_session_with_tenant(tenant_id) as db:
            projects = await db.execute(select(Project))
            # Solo retorna proyectos del tenant_id especificado
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _session_factory() as session:
        try:
            # Configurar RLS para este tenant
            await session.execute(
                text("SET app.current_tenant = :tenant_id"),
                {"tenant_id": str(tenant_id)}
            )
            
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Limpiar configuración de tenant
            await session.execute(text("RESET app.current_tenant"))


class TenantSession:
    """
    Wrapper para sesión con tenant automático.
    
    Uso:
        db = TenantSession(session, tenant_id)
        await db.execute(select(Project))  # Automáticamente filtrado por tenant
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._initialized = False
    
    async def _ensure_tenant_set(self) -> None:
        """Asegura que el tenant esté configurado en la sesión."""
        if not self._initialized:
            await self._session.execute(
                text("SET app.current_tenant = :tenant_id"),
                {"tenant_id": str(self._tenant_id)}
            )
            self._initialized = True
    
    async def execute(self, *args, **kwargs):
        await self._ensure_tenant_set()
        return await self._session.execute(*args, **kwargs)
    
    async def scalar(self, *args, **kwargs):
        await self._ensure_tenant_set()
        return await self._session.scalar(*args, **kwargs)
    
    async def scalars(self, *args, **kwargs):
        await self._ensure_tenant_set()
        return await self._session.scalars(*args, **kwargs)
    
    def add(self, instance):
        return self._session.add(instance)
    
    def add_all(self, instances):
        return self._session.add_all(instances)
    
    async def delete(self, instance):
        await self._ensure_tenant_set()
        return await self._session.delete(instance)
    
    async def commit(self):
        return await self._session.commit()
    
    async def rollback(self):
        return await self._session.rollback()
    
    async def refresh(self, instance):
        return await self._session.refresh(instance)
