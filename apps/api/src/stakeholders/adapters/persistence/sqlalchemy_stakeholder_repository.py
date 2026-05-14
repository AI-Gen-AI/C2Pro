"""
SQLAlchemy implementation of the IStakeholderRepository port.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.approval import ApprovalStatus
from src.projects.adapters.persistence.models import ProjectORM
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.stakeholders.domain.models import RaciAssignment, RACIRole, Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class SqlAlchemyStakeholderRepository(IStakeholderRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _normalize_naive_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    async def _get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        """Get tenant_id for a project."""
        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # --- Mapper helpers ---
    def _to_domain(self, orm: StakeholderORM) -> Stakeholder:
        return Stakeholder(
            id=orm.id,
            project_id=orm.project_id,
            name=orm.name,
            role=orm.role,
            organization=orm.organization,
            department=orm.department,
            power_level=orm.power_level,
            interest_level=orm.interest_level,
            quadrant=orm.quadrant,
            email=orm.email,
            phone=orm.phone,
            source_clause_id=orm.source_clause_id,
            extracted_from_document_id=orm.extracted_from_document_id,
            approval_status=str(orm.approval_status),
            reviewed_by=orm.reviewed_by,
            reviewed_at=orm.reviewed_at,
            review_comment=orm.review_comment,
            stakeholder_metadata=orm.stakeholder_metadata or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: Stakeholder) -> StakeholderORM:
        approval_status = (
            ApprovalStatus(domain.approval_status)
            if isinstance(domain.approval_status, str)
            else domain.approval_status
        )
        return StakeholderORM(
            id=domain.id,
            project_id=domain.project_id,
            name=domain.name,
            role=domain.role,
            organization=domain.organization,
            department=domain.department,
            power_level=domain.power_level,
            interest_level=domain.interest_level,
            quadrant=domain.quadrant,
            email=domain.email,
            phone=domain.phone,
            source_clause_id=domain.source_clause_id,
            extracted_from_document_id=domain.extracted_from_document_id,
            approval_status=approval_status,
            reviewed_by=domain.reviewed_by,
            reviewed_at=self._normalize_naive_utc(domain.reviewed_at),
            review_comment=domain.review_comment,
            stakeholder_metadata=domain.stakeholder_metadata,
            created_at=self._normalize_naive_utc(domain.created_at),
            updated_at=self._normalize_naive_utc(domain.updated_at),
        )

    def _to_raci_domain(self, orm: StakeholderWBSRaciORM) -> RaciAssignment:
        return RaciAssignment(
            id=orm.id,
            project_id=orm.project_id,
            stakeholder_id=orm.stakeholder_id,
            wbs_item_id=orm.wbs_item_id,
            raci_role=orm.raci_role,
            evidence_text=orm.evidence_text,
            generated_automatically=orm.generated_automatically,
            manually_verified=orm.manually_verified,
            verified_by=orm.verified_by,
            verified_at=orm.verified_at,
            created_at=orm.created_at,
        )

    def _to_raci_orm(self, assignment: RaciAssignment) -> StakeholderWBSRaciORM:
        return StakeholderWBSRaciORM(
            id=assignment.id,
            project_id=assignment.project_id,
            stakeholder_id=assignment.stakeholder_id,
            wbs_item_id=assignment.wbs_item_id,
            raci_role=assignment.raci_role,
            evidence_text=assignment.evidence_text,
            generated_automatically=assignment.generated_automatically,
            manually_verified=assignment.manually_verified,
            verified_by=assignment.verified_by,
            verified_at=assignment.verified_at,
            created_at=assignment.created_at,
        )

    async def add(self, stakeholder: Stakeholder, tenant_id: UUID) -> None:
        if tenant_id is not None:
            proj_tenant = await self._get_project_tenant_id(stakeholder.project_id)
            if proj_tenant is None or proj_tenant != tenant_id:
                raise PermissionError("Cannot add stakeholder for project outside tenant")
        self.session.add(self._to_orm(stakeholder))

    async def get_by_id(
        self, stakeholder_id: UUID, tenant_id: UUID
    ) -> Stakeholder | None:
        """Get stakeholder by ID with explicit tenant isolation."""
        stmt = (
            select(StakeholderORM)
            .join(ProjectORM, StakeholderORM.project_id == ProjectORM.id)
            .where(
                StakeholderORM.id == stakeholder_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_all_stakeholders(self, tenant_id: UUID) -> list[Stakeholder]:
        """List all stakeholders for a tenant."""
        stmt = (
            select(StakeholderORM)
            .join(ProjectORM, StakeholderORM.project_id == ProjectORM.id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        return [self._to_domain(item) for item in items]

    async def get_stakeholders_by_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Stakeholder], int]:
        """List stakeholders for a tenant-scoped project with pagination."""
        stmt = (
            select(StakeholderORM)
            .join(ProjectORM, StakeholderORM.project_id == ProjectORM.id)
            .where(
                StakeholderORM.project_id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(StakeholderORM)
            .join(ProjectORM, StakeholderORM.project_id == ProjectORM.id)
            .where(
                StakeholderORM.project_id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )

        result = await self.session.execute(stmt)
        items = result.scalars().all()

        total_count_result = await self.session.execute(count_stmt)
        total_count = total_count_result.scalar_one_or_none() or 0

        return [self._to_domain(item) for item in items], total_count

    async def update(self, stakeholder: Stakeholder, tenant_id: UUID) -> None:
        """Update stakeholder metadata."""
        orm = await self.session.get(StakeholderORM, stakeholder.id)
        if orm is None:
            return

        # Verify ownership if tenant_id is provided
        if tenant_id is not None:
            proj_tenant = await self._get_project_tenant_id(orm.project_id)
            if proj_tenant is None or proj_tenant != tenant_id:
                raise PermissionError("Cannot update stakeholder for project outside tenant")

        orm.name = stakeholder.name
        orm.role = stakeholder.role
        orm.organization = stakeholder.organization
        orm.department = stakeholder.department
        orm.power_level = stakeholder.power_level
        orm.interest_level = stakeholder.interest_level
        orm.quadrant = stakeholder.quadrant
        orm.email = stakeholder.email
        orm.phone = stakeholder.phone
        orm.source_clause_id = stakeholder.source_clause_id
        orm.extracted_from_document_id = stakeholder.extracted_from_document_id
        orm.approval_status = stakeholder.approval_status
        orm.reviewed_by = stakeholder.reviewed_by
        orm.reviewed_at = self._normalize_naive_utc(stakeholder.reviewed_at)
        orm.review_comment = stakeholder.review_comment
        orm.stakeholder_metadata = stakeholder.stakeholder_metadata

        await self.session.flush()

    async def delete(self, stakeholder_id: UUID, tenant_id: UUID) -> None:
        """Delete a stakeholder."""
        orm = await self.get_by_id(stakeholder_id=stakeholder_id, tenant_id=tenant_id)
        if orm:
            orm_to_delete = await self.session.get(StakeholderORM, orm.id)
            if orm_to_delete:
                await self.session.delete(orm_to_delete)
                await self.session.flush()

    async def add_raci_assignment(
        self, assignment: RaciAssignment, tenant_id: UUID
    ) -> None:
        """Add a RACI assignment."""
        if tenant_id is not None:
            proj_tenant = await self._get_project_tenant_id(assignment.project_id)
            if proj_tenant is None or proj_tenant != tenant_id:
                raise PermissionError("Cannot add RACI assignment for project outside tenant")
        self.session.add(self._to_raci_orm(assignment))
        await self.session.flush()

    async def list_raci_assignments(
        self, project_id: UUID, tenant_id: UUID
    ) -> list[RaciAssignment]:
        """List RACI assignments for a tenant-scoped project."""
        stmt = (
            select(StakeholderWBSRaciORM)
            .join(ProjectORM, StakeholderWBSRaciORM.project_id == ProjectORM.id)
            .where(
                StakeholderWBSRaciORM.project_id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_raci_domain(row) for row in rows]

    async def get_raci_assignment(
        self,
        project_id: UUID,
        wbs_item_id: UUID,
        stakeholder_id: UUID,
        tenant_id: UUID,
    ) -> RaciAssignment | None:
        """Get a tenant-scoped RACI assignment."""
        stmt = (
            select(StakeholderWBSRaciORM)
            .join(ProjectORM, StakeholderWBSRaciORM.project_id == ProjectORM.id)
            .where(
                StakeholderWBSRaciORM.project_id == project_id,
                StakeholderWBSRaciORM.wbs_item_id == wbs_item_id,
                StakeholderWBSRaciORM.stakeholder_id == stakeholder_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_raci_domain(orm) if orm else None

    async def get_accountable_assignment(
        self,
        project_id: UUID,
        wbs_item_id: UUID,
        tenant_id: UUID,
        exclude_stakeholder_id: UUID | None = None,
    ) -> RaciAssignment | None:
        """Get the ACCOUNTABLE stakeholder for a tenant-scoped WBS item."""
        stmt = (
            select(StakeholderWBSRaciORM)
            .join(ProjectORM, StakeholderWBSRaciORM.project_id == ProjectORM.id)
            .where(
                StakeholderWBSRaciORM.project_id == project_id,
                StakeholderWBSRaciORM.wbs_item_id == wbs_item_id,
                StakeholderWBSRaciORM.raci_role == RACIRole.ACCOUNTABLE,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        if exclude_stakeholder_id:
            stmt = stmt.where(StakeholderWBSRaciORM.stakeholder_id != exclude_stakeholder_id)

        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_raci_domain(orm) if orm else None

    async def update_raci_assignment(
        self, assignment: RaciAssignment, tenant_id: UUID
    ) -> None:
        """Update a RACI assignment."""
        orm = await self.session.get(StakeholderWBSRaciORM, assignment.id)
        if not orm:
            return
        if tenant_id is not None:
            proj_tenant = await self._get_project_tenant_id(orm.project_id)
            if proj_tenant is None or proj_tenant != tenant_id:
                raise PermissionError("Cannot update RACI assignment for project outside tenant")
        orm.raci_role = assignment.raci_role
        orm.evidence_text = assignment.evidence_text
        orm.generated_automatically = assignment.generated_automatically
        orm.manually_verified = assignment.manually_verified
        orm.verified_by = assignment.verified_by
        orm.verified_at = assignment.verified_at
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: object) -> None:
        if isinstance(entity, Stakeholder):
            orm = await self.session.get(StakeholderORM, entity.id)
            if orm:
                await self.session.refresh(orm)
                entity.name = orm.name
                entity.role = orm.role
                entity.organization = orm.organization
                entity.department = orm.department
                entity.power_level = orm.power_level
                entity.interest_level = orm.interest_level
                entity.quadrant = orm.quadrant
                entity.email = orm.email
                entity.phone = orm.phone
                entity.source_clause_id = orm.source_clause_id
                entity.extracted_from_document_id = orm.extracted_from_document_id
                entity.approval_status = str(orm.approval_status)
                entity.reviewed_by = orm.reviewed_by
                entity.reviewed_at = orm.reviewed_at
                entity.review_comment = orm.review_comment
                entity.stakeholder_metadata = orm.stakeholder_metadata or {}
                entity.created_at = orm.created_at
                entity.updated_at = orm.updated_at
        if isinstance(entity, RaciAssignment):
            orm = await self.session.get(StakeholderWBSRaciORM, entity.id)
            if orm:
                await self.session.refresh(orm)
                entity.raci_role = orm.raci_role
                entity.evidence_text = orm.evidence_text
                entity.generated_automatically = orm.generated_automatically
                entity.manually_verified = orm.manually_verified
                entity.verified_by = orm.verified_by
                entity.verified_at = orm.verified_at
