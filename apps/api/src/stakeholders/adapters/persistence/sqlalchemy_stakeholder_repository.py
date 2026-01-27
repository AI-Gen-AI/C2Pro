"""
SQLAlchemy implementation of the IStakeholderRepository port.
"""
from __future__ import annotations

from typing import List, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.approval import ApprovalStatus
from src.stakeholders.domain.models import Stakeholder, RaciAssignment
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM


class SqlAlchemyStakeholderRepository(IStakeholderRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

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
            reviewed_at=domain.reviewed_at,
            review_comment=domain.review_comment,
            stakeholder_metadata=domain.stakeholder_metadata,
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

    async def add(self, stakeholder: Stakeholder) -> None:
        self.session.add(self._to_orm(stakeholder))

    async def get_by_id(self, stakeholder_id: UUID) -> Stakeholder | None:
        result = await self.session.execute(
            select(StakeholderORM).where(StakeholderORM.id == stakeholder_id)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_stakeholders_by_project(
        self, project_id: UUID, skip: int = 0, limit: int = 100
    ) -> Tuple[List[Stakeholder], int]:
        stmt = (
            select(StakeholderORM)
            .where(StakeholderORM.project_id == project_id)
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).where(StakeholderORM.project_id == project_id)

        result = await self.session.execute(stmt)
        items = result.scalars().all()

        total_count_result = await self.session.execute(count_stmt)
        total_count = total_count_result.scalar_one()

        return [self._to_domain(item) for item in items], total_count

    async def update(self, stakeholder: Stakeholder) -> None:
        orm = await self.session.get(StakeholderORM, stakeholder.id)
        if orm is None:
            return
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
        orm.reviewed_at = stakeholder.reviewed_at
        orm.review_comment = stakeholder.review_comment
        orm.stakeholder_metadata = stakeholder.stakeholder_metadata

    async def delete(self, stakeholder_id: UUID) -> None:
        orm = await self.session.get(StakeholderORM, stakeholder_id)
        if orm:
            await self.session.delete(orm)

    async def add_raci_assignment(self, assignment: RaciAssignment) -> None:
        self.session.add(self._to_raci_orm(assignment))

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
