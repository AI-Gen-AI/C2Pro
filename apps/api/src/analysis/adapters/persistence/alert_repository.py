from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import String, and_, case, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.analysis.adapters.persistence.models import Alert
from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AlertType
from src.analysis.ports.alert_repository import AlertRepository
from src.analysis.ports.types import AlertRecord
from src.core.pagination import (
    InvalidCursorException,
    Page,
    decode_cursor,
    encode_cursor,
)
from src.projects.adapters.persistence.models import ProjectORM


def _severity_rank_expression() -> ColumnElement[int]:
    """Stable severity ordering shared by the list cursor and SQL ORDER BY."""
    severity_text = cast(Alert.severity, String)
    return case(
        (severity_text == AlertSeverity.CRITICAL.value, 0),
        (severity_text == AlertSeverity.HIGH.value, 1),
        (severity_text == AlertSeverity.MEDIUM.value, 2),
        (severity_text == AlertSeverity.LOW.value, 3),
        else_=4,
    )


def _severity_rank_value(severity: AlertSeverity | str) -> int:
    normalized = severity.value if isinstance(severity, AlertSeverity) else str(severity).lower()
    return {
        AlertSeverity.CRITICAL.value: 0,
        AlertSeverity.HIGH.value: 1,
        AlertSeverity.MEDIUM.value: 2,
        AlertSeverity.LOW.value: 3,
    }.get(normalized, 4)


def _encode_alert_cursor(alert: Alert) -> str:
    return encode_cursor(
        f"{_severity_rank_value(alert.severity)}|{alert.created_at.isoformat()}|{alert.id}"
    )


def _decode_alert_cursor(cursor: str) -> tuple[int, datetime, UUID]:
    try:
        rank_raw, created_raw, alert_id_raw = decode_cursor(cursor).split("|", 2)
        rank = int(rank_raw)
        created_at = datetime.fromisoformat(created_raw)
        alert_id = UUID(alert_id_raw)
    except (ValueError, TypeError) as exc:
        raise InvalidCursorException("Invalid alert cursor") from exc
    if rank < 0 or rank > 4:
        raise InvalidCursorException("Invalid alert cursor")
    return rank, created_at, alert_id


class SqlAlchemyAlertRepository(AlertRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID | None = None,
        alert_type: AlertType | None = None,
        severities: list[AlertSeverity] | None = None,
        statuses: list[AlertStatus] | None = None,
        category: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> Page[AlertRecord]:
        query = select(Alert).where(Alert.project_id == project_id)
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Alert.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )

        if severities:
            query = query.where(Alert.severity.in_(severities))
        if statuses:
            query = query.where(Alert.status.in_(statuses))
        if category:
            query = query.where(Alert.category == category)
        if alert_type:
            query = query.where(Alert.alert_type == alert_type)

        severity_rank = _severity_rank_expression()
        if cursor:
            cursor_rank, cursor_created_at, cursor_id = _decode_alert_cursor(cursor)
            query = query.where(
                or_(
                    severity_rank > cursor_rank,
                    and_(
                        severity_rank == cursor_rank,
                        Alert.created_at < cursor_created_at,
                    ),
                    and_(
                        severity_rank == cursor_rank,
                        Alert.created_at == cursor_created_at,
                        Alert.id < cursor_id,
                    ),
                )
            )

        query = query.order_by(
            severity_rank.asc(),
            Alert.created_at.desc(),
            Alert.id.desc(),
        ).limit(limit + 1)
        result = await self.session.scalars(query)
        items = list(result.all())

        has_more = len(items) > limit
        items = items[:limit]
        next_cursor = _encode_alert_cursor(items[-1]) if has_more and items else None
        # Avoid materializing Page[AlertRecord] at runtime: AlertRecord is a
        # Protocol used for static typing, not a Pydantic schema.
        return Page(
            items=cast(list[AlertRecord], items),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def get_stats(self, project_id: UUID, tenant_id: UUID | None = None) -> dict[str, int]:
        query = select(Alert).where(Alert.project_id == project_id)
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Alert.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )
        result = await self.session.execute(
            query
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

    async def get_by_id(
        self, alert_id: UUID, tenant_id: UUID | None = None
    ) -> AlertRecord | None:
        query = select(Alert).where(Alert.id == alert_id)
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Alert.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )
        result = await self.session.execute(query)
        return cast(AlertRecord | None, result.scalar_one_or_none())

    async def create(self, payload: AlertCreate) -> AlertRecord:
        project = await self.session.scalar(
            select(ProjectORM).where(ProjectORM.id == payload.project_id)
        )
        if project is None:
            raise ValueError("Cannot create alert for unknown project")

        alert = Alert(
            tenant_id=project.tenant_id,
            project_id=payload.project_id,
            analysis_id=payload.analysis_id,
            severity=payload.severity,
            alert_type=payload.alert_type,
            category=payload.category,
            rule_id=payload.rule_id,
            title=payload.title,
            message=payload.description,
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
        return cast(AlertRecord, alert)

    async def update(self, alert: AlertRecord) -> None:
        self.session.add(alert)

    async def delete(self, alert_id: UUID, tenant_id: UUID | None = None) -> bool:
        alert = await self.get_by_id(alert_id=alert_id, tenant_id=tenant_id)
        if not alert:
            return False
        await self.session.delete(alert)
        return True

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)
