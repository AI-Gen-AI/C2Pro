"""
Cookie Consent Repository.

Persistence layer for GDPR cookie consent records.
Refers to TASK-REV-020.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.frontend_support.models import CookieConsentORM


class CookieConsentRepository:
    """
    Repository for cookie consent persistence.

    Provides async database operations for consent records.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_consent(
        self,
        tenant_id: UUID,
        user_id: str,
        version: str,
    ) -> CookieConsentORM | None:
        """Get consent record by tenant, user, and version."""
        stmt = select(CookieConsentORM).where(
            CookieConsentORM.tenant_id == tenant_id,
            CookieConsentORM.user_id == user_id,
            CookieConsentORM.version == version,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_consent(
        self,
        tenant_id: UUID,
        user_id: str,
        version: str,
        categories: dict[str, Any],
    ) -> CookieConsentORM:
        """Create a new consent record."""
        consent = CookieConsentORM(
            tenant_id=tenant_id,
            user_id=user_id,
            version=version,
            categories=categories,
        )
        self.session.add(consent)
        await self.session.flush()
        return consent

    async def update_consent(
        self,
        tenant_id: UUID,
        user_id: str,
        version: str,
        categories: dict[str, Any],
    ) -> CookieConsentORM | None:
        """Update an existing consent record."""
        consent = await self.get_consent(tenant_id, user_id, version)
        if consent:
            consent.categories = categories
            await self.session.flush()
        return consent

    async def upsert_consent(
        self,
        tenant_id: UUID,
        user_id: str,
        version: str,
        categories: dict[str, Any],
    ) -> CookieConsentORM:
        """Create or update a consent record."""
        existing = await self.get_consent(tenant_id, user_id, version)
        if existing:
            existing.categories = categories
            await self.session.flush()
            return existing
        return await self.create_consent(tenant_id, user_id, version, categories)
