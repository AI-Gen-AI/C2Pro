
from __future__ import annotations
from uuid import UUID
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.auth.models import Tenant

logger = structlog.get_logger()

async def get_tenant_by_id(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """
    Obtiene un tenant por ID.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    return result.scalar_one_or_none()

class TenantService:
    pass
