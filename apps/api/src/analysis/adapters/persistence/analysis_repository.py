from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.analysis.ports.analysis_repository import IAnalysisRepository
from src.analysis.ports.types import AlertWrite, AnalysisRecord, AnalysisWrite
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyAnalysisRepository(IAnalysisRepository):
    def __init__(self, session: AsyncSession, tenant_id: UUID | None = None):
        self.session = session
        self.tenant_id = tenant_id

    async def _verify_project_ownership(
        self, project_id: UUID, tenant_id: UUID
    ) -> bool:
        """Verify that a project belongs to the given tenant.

        ``tenant_id`` is the caller-supplied, per-call tenant -- not
        ``self.tenant_id`` -- so this check cannot be bypassed by
        constructing the repository without a tenant.
        """
        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self.session.execute(stmt)
        project_tenant = result.scalar_one_or_none()
        if project_tenant is None:
            return False
        return project_tenant == tenant_id

    async def get_result_json(
        self, analysis_id: UUID, tenant_id: UUID
    ) -> dict[str, Any] | None:
        """Exact tenant-scoped read of one analysis' ``result_json`` (snapshot lineage)."""
        stmt = select(Analysis.result_json).where(
            Analysis.id == analysis_id,
            Analysis.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add_analysis(self, analysis: AnalysisWrite, tenant_id: UUID) -> None:
        """Persist an analysis.

        ``tenant_id`` is mandatory and always verified against both the
        DTO's own tenant and its project's ownership -- there is no code
        path where verification is silently skipped for lack of context.
        """
        owns_project = await self._verify_project_ownership(
            analysis.project_id, tenant_id
        )
        if analysis.tenant_id != tenant_id or not owns_project:
            raise PermissionError("Cannot add analysis for project outside tenant")
        self.session.add(Analysis(**analysis.__dict__))

    async def add_alerts(self, alerts: Iterable[AlertWrite], tenant_id: UUID) -> None:
        """Persist alerts. Ownership is verified per-alert; see ``add_analysis``."""
        alert_list = list(alerts)
        for alert in alert_list:
            owns_project = await self._verify_project_ownership(
                alert.project_id, tenant_id
            )
            if alert.tenant_id != tenant_id or not owns_project:
                raise PermissionError("Cannot add alert for project outside tenant")
        self.session.add_all([Alert(**alert.__dict__) for alert in alert_list])

    async def list_recent(
        self, *, limit: int, offset: int, tenant_id: UUID | None = None
    ) -> list[AnalysisRecord]:
        query = select(Analysis)
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Analysis.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )
        result = await self.session.execute(
            query.order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
        )
        return cast(list[AnalysisRecord], list(result.scalars().all()))

    async def count_all(self, tenant_id: UUID | None = None) -> int:
        query = select(func.count(Analysis.id))
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Analysis.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )
        total = await self.session.scalar(query)
        return int(total or 0)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
