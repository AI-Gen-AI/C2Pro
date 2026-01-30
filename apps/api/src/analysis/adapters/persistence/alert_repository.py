from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.analysis.application.dtos import AlertCreate
from src.analysis.ports.alert_repository import AlertRepository
from src.core.pagination import Page, paginate


class SqlAlchemyAlertRepository(AlertRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_project(
        self,
        project_id: UUID,
        severities: Optional[List[AlertSeverity]] = None,
        statuses: Optional[List[AlertStatus]] = None,
        category: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Page[Alert]:
        query = select(Alert).where(Alert.project_id == project_id)

        if severities:
            query = query.where(Alert.severity.in_(severities))
        if statuses:
            query = query.where(Alert.status.in_(statuses))
        if category:
            query = query.where(Alert.category == category)

        query = query.order_by(Alert.severity.desc(), Alert.created_at.desc())

        return await paginate(
            query=query,
            model=Alert,
            cursor=cursor,
            limit=limit,
            order_by="created_at",
            order_direction="desc",
        )

    async def get_stats(self, project_id: UUID) -> dict[str, int]:
        result = await self.session.execute(
            select(Alert).where(Alert.project_id == project_id)
        )
        alerts = result.scalars().all()

        return {
            "total": len(alerts),
            "open": sum(1 for a in alerts if a.status == AlertStatus.OPEN),
            "resolved": sum(1 for a in alerts if a.status == AlertStatus.RESOLVED),
            "dismissed": sum(1 for a in alerts if a.status == AlertStatus.DISMISSED),
            "critical": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
            "high": sum(1 for a in alerts if a.severity == AlertSeverity.HIGH),
            "medium": sum(1 for a in alerts if a.severity == AlertSeverity.MEDIUM),
            "low": sum(1 for a in alerts if a.severity == AlertSeverity.LOW),
        }

    async def get_by_id(self, alert_id: UUID) -> Alert | None:
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def create(self, payload: AlertCreate) -> Alert:
        alert = Alert(
            project_id=payload.project_id,
            analysis_id=payload.analysis_id,
            severity=payload.severity,
            category=payload.category,
            rule_id=payload.rule_id,
            title=payload.title,
            description=payload.description,
            recommendation=payload.recommendation,
            source_clause_id=payload.source_clause_id,
            related_clause_ids=payload.related_clause_ids,
            affected_entities=payload.affected_entities,
            impact_level=payload.impact_level,
            alert_metadata=payload.alert_metadata,
            status=AlertStatus.OPEN,
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def update(self, alert: Alert) -> None:
        self.session.add(alert)

    async def delete(self, alert_id: UUID) -> bool:
        alert = await self.session.get(Alert, alert_id)
        if not alert:
            return False
        await self.session.delete(alert)
        return True

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)
