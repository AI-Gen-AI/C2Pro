"""
SQLAlchemy Alert Repository.

Persistence adapter using AlertORM from analysis module.
Implements IAlertRepository port with tenant isolation.

Refers to Suite ID: TS-E2E-FLW-JRN-001, TS-BUG-ALRT-IMPORT-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.application.ports.alert_repository import IAlertRepository
from src.alerts.domain.enums import AlertSeverity, AlertStatus
from src.alerts.domain.models import Alert
from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.documents.adapters.persistence.models import ClauseORM
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyAlertRepository(IAlertRepository):
    """SQLAlchemy implementation of IAlertRepository with tenant isolation."""

    def __init__(self, session: AsyncSession, tenant_id: UUID | None = None) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def _verify_project_ownership(self, project_id: UUID) -> bool:
        """Verify that a project belongs to the current tenant."""
        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self._session.execute(stmt)
        project_tenant = result.scalar_one_or_none()
        if project_tenant is None:
            return False
        if self._tenant_id is None:
            return True
        return project_tenant == self._tenant_id

    def _to_domain(self, orm_alert: AlertORM) -> Alert:
        """Convert ORM model to domain entity."""
        severity_value = getattr(orm_alert.severity, "value", orm_alert.severity)
        status_value = getattr(orm_alert.status, "value", orm_alert.status)

        try:
            severity = AlertSeverity(str(severity_value).lower())
        except ValueError:
            severity = AlertSeverity.MEDIUM

        try:
            status = AlertStatus(str(status_value).lower())
        except ValueError:
            status = AlertStatus.OPEN

        return Alert(
            id=orm_alert.id,
            project_id=orm_alert.project_id,
            severity=severity,
            category=orm_alert.category or "risk",
            status=status,
            approval_status=orm_alert.approval_status,
            rule_id=orm_alert.rule_id,
            title=orm_alert.title,
            description=orm_alert.description or "",
            affected_entities=orm_alert.affected_entities or {},
            alert_metadata=orm_alert.alert_metadata or {},
            created_at=orm_alert.created_at,
            updated_at=orm_alert.updated_at,
            reviewed_by=orm_alert.reviewed_by,
            reviewed_at=orm_alert.reviewed_at,
            review_comment=getattr(orm_alert, "review_comment", None),
            resolved_at=orm_alert.resolved_at,
            resolved_by=orm_alert.resolved_by,
            resolution_notes=getattr(orm_alert, "resolution_notes", None),
            source_clause_id=orm_alert.source_clause_id,
        )

    @staticmethod
    def _normalize_naive_utc(value: datetime | None) -> datetime | None:
        """Normalize aware datetimes for naive TIMESTAMP columns."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _to_orm(self, domain_alert: Alert) -> AlertORM:
        """Convert domain entity to ORM model (for updates)."""
        return AlertORM(
            id=domain_alert.id,
            project_id=domain_alert.project_id,
            severity=domain_alert.severity.value
                if hasattr(domain_alert.severity, "value")
                else domain_alert.severity,
            category=domain_alert.category,
            status=domain_alert.status.value
                if hasattr(domain_alert.status, "value")
                else domain_alert.status,
            rule_id=domain_alert.rule_id,
            title=domain_alert.title,
            description=domain_alert.description,
            affected_entities=domain_alert.affected_entities,
            alert_metadata=domain_alert.alert_metadata,
            created_at=self._normalize_naive_utc(domain_alert.created_at),
            updated_at=self._normalize_naive_utc(domain_alert.updated_at or datetime.now(UTC)),
            reviewed_by=domain_alert.reviewed_by,
            reviewed_at=self._normalize_naive_utc(domain_alert.reviewed_at),
            resolved_at=self._normalize_naive_utc(domain_alert.resolved_at),
            resolved_by=domain_alert.resolved_by,
            source_clause_id=domain_alert.source_clause_id,
        )

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:
        """Get alert by ID with tenant isolation."""
        query = (
            select(AlertORM)
            .join(ProjectORM, ProjectORM.id == AlertORM.project_id)
            .where(
                AlertORM.id == alert_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        result = await self._session.execute(query)
        orm_alert = result.scalar_one_or_none()
        return self._to_domain(orm_alert) if orm_alert else None

    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        status: AlertStatus | None = None,
        category: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """List alerts for a project with filters and tenant isolation."""
        query = (
            select(AlertORM)
            .join(ProjectORM, ProjectORM.id == AlertORM.project_id)
            .where(
                AlertORM.project_id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        if status:
            query = query.where(AlertORM.status == status.value)
        if category:
            query = query.where(AlertORM.category == category)
        if severity:
            query = query.where(AlertORM.severity == severity.value)

        query = query.order_by(AlertORM.created_at.desc())
        result = await self._session.execute(query)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        status: AlertStatus | None = None,
        category: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """List alerts for a tenant with optional filters."""
        query = (
            select(AlertORM)
            .join(ProjectORM, ProjectORM.id == AlertORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        if project_id:
            query = query.where(AlertORM.project_id == project_id)
        if document_id:
            query = query.join(
                ClauseORM, ClauseORM.id == AlertORM.source_clause_id
            ).where(ClauseORM.document_id == document_id)
        if status:
            query = query.where(AlertORM.status == status.value)
        if category:
            query = query.where(AlertORM.category == category)
        if severity:
            query = query.where(AlertORM.severity == severity.value)

        query = query.order_by(AlertORM.created_at.desc())
        result = await self._session.execute(query)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def create(self, alert: Alert, tenant_id: UUID | None = None) -> Alert:
        """Create a new alert with tenant verification."""
        effective_tenant_id = tenant_id or self._tenant_id
        if effective_tenant_id is not None:  # noqa: SIM102
            if not await self._verify_project_ownership(alert.project_id):
                raise PermissionError("Cannot create alert for project outside tenant")
        orm_alert = AlertORM(
            id=alert.id,
            project_id=alert.project_id,
            severity=alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
            category=alert.category,
            status=alert.status.value if hasattr(alert.status, "value") else alert.status,
            rule_id=alert.rule_id,
            title=alert.title,
            description=alert.description,
            affected_entities=alert.affected_entities,
            alert_metadata=alert.alert_metadata,
            created_at=self._normalize_naive_utc(alert.created_at),
            source_clause_id=alert.source_clause_id,
        )
        self._session.add(orm_alert)
        await self._session.flush()
        return alert

    async def save(self, alert: Alert, tenant_id: UUID | None = None) -> None:
        """Save changes to an alert with tenant verification."""
        effective_tenant_id = tenant_id or self._tenant_id
        orm_alert = await self._session.get(AlertORM, alert.id)
        if orm_alert:
            if effective_tenant_id is not None:  # noqa: SIM102
                if not await self._verify_project_ownership(orm_alert.project_id):
                    raise PermissionError("Cannot save alert for project outside tenant")
            orm_alert.status = alert.status.value if hasattr(alert.status, "value") else alert.status
            orm_alert.reviewed_by = alert.reviewed_by
            orm_alert.reviewed_at = self._normalize_naive_utc(alert.reviewed_at)
            orm_alert.resolved_at = self._normalize_naive_utc(alert.resolved_at)
            orm_alert.resolved_by = alert.resolved_by
            orm_alert.alert_metadata = alert.alert_metadata
            orm_alert.updated_at = self._normalize_naive_utc(datetime.now(UTC))

    async def delete(self, alert_id: UUID, tenant_id: UUID) -> bool:
        """Delete an alert with tenant isolation."""
        query = (
            select(AlertORM)
            .join(ProjectORM, ProjectORM.id == AlertORM.project_id)
            .where(
                AlertORM.id == alert_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        result = await self._session.execute(query)
        orm_alert = result.scalar_one_or_none()
        if orm_alert:
            await self._session.delete(orm_alert)
            return True
        return False

    async def commit(self) -> None:
        """Commit pending changes."""
        await self._session.commit()
