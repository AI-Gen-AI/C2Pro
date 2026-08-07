"""
Frontend support repositories.

CookieConsentRepository       — GDPR cookie consent (TASK-REV-020).
DisclaimerAcceptanceRepository — Gate-8 disclaimer persistence (SEC-014).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.frontend_support.models import CookieConsentORM, DisclaimerAcceptanceORM


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


class DisclaimerAcceptanceRepository:
    """Persistence layer for gate-8 legal disclaimer acceptances (SEC-014)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_acceptance(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        project_id: str,
        version: str,
    ) -> DisclaimerAcceptanceORM | None:
        stmt = select(DisclaimerAcceptanceORM).where(
            DisclaimerAcceptanceORM.tenant_id == tenant_id,
            DisclaimerAcceptanceORM.user_id == user_id,
            DisclaimerAcceptanceORM.project_id == project_id,
            DisclaimerAcceptanceORM.version == version,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def accept(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        project_id: str,
        version: str,
    ) -> DisclaimerAcceptanceORM:
        stmt = (
            pg_insert(DisclaimerAcceptanceORM)
            .values(tenant_id=tenant_id, user_id=user_id, project_id=project_id, version=version)
            .on_conflict_do_nothing(
                constraint="uq_disclaimer_acceptance",
            )
            .returning(DisclaimerAcceptanceORM)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            existing = await self.get_acceptance(
                tenant_id=tenant_id, user_id=user_id, project_id=project_id, version=version
            )
            return existing  # type: ignore[return-value]
        return row
