"""
Compatibility service API for project tests.

Refers to Suite ID: TS-UA-PRJ-UC-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictError, NotFoundError
from src.projects.adapters.persistence.models import ProjectORM
from src.projects.application.dtos import ProjectCreateRequest, ProjectFilters, ProjectUpdateRequest
from src.projects.domain.models import ProjectStatus


@dataclass(slots=True)
class ProjectListPage:
    items: list[ProjectORM]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass(slots=True)
class ProjectStats:
    total_projects: int
    active_projects: int
    draft_projects: int
    completed_projects: int
    archived_projects: int
    avg_coherence_score: float | None


def _attach_metadata_alias(project: ProjectORM) -> ProjectORM:
    # Backward-compatible alias expected by legacy tests.
    project.project_metadata = project.metadata_json or {}
    return project


async def get_project_by_id(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> ProjectORM | None:
    result = await db.execute(
        select(ProjectORM).where(
            ProjectORM.id == project_id,
            ProjectORM.tenant_id == tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    return _attach_metadata_alias(project) if project is not None else None


async def get_project_by_code(db: AsyncSession, code: str, tenant_id: UUID) -> ProjectORM | None:
    result = await db.execute(
        select(ProjectORM).where(
            ProjectORM.code == code,
            ProjectORM.tenant_id == tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    return _attach_metadata_alias(project) if project is not None else None


class ProjectService:
    @staticmethod
    async def create_project(
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,  # kept for API compatibility
        request: ProjectCreateRequest,
    ) -> ProjectORM:
        del user_id
        if request.code:
            existing = await get_project_by_code(db, request.code, tenant_id)
            if existing is not None:
                raise ConflictError("Project", "code", request.code)

        project = ProjectORM(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            code=request.code,
            project_type=request.project_type.value,
            status=ProjectStatus.DRAFT.value,
            estimated_budget=request.estimated_budget,
            currency=request.currency,
            start_date=request.start_date,
            end_date=request.end_date,
            metadata_json=request.metadata or {},
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return _attach_metadata_alias(project)

    @staticmethod
    async def get_project(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> ProjectORM:
        project = await get_project_by_id(db, project_id, tenant_id)
        if project is None:
            raise NotFoundError("Project")
        return project

    @staticmethod
    async def list_projects(
        db: AsyncSession,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: ProjectFilters | None = None,
    ) -> ProjectListPage:
        query = select(ProjectORM).where(ProjectORM.tenant_id == tenant_id)
        if filters:
            if filters.status is not None:
                query = query.where(ProjectORM.status == filters.status.value)
            if filters.project_type is not None:
                query = query.where(ProjectORM.project_type == filters.project_type.value)
            if filters.search:
                search = f"%{filters.search}%"
                query = query.where(
                    (ProjectORM.name.ilike(search))
                    | (ProjectORM.code.ilike(search))
                    | (ProjectORM.description.ilike(search))
                )
            if filters.created_after is not None:
                query = query.where(ProjectORM.created_at >= filters.created_after)
            if filters.created_before is not None:
                query = query.where(ProjectORM.created_at <= filters.created_before)

        total_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = int(total_result.scalar() or 0)

        paged_query = (
            query.order_by(ProjectORM.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(paged_query)
        items = [_attach_metadata_alias(item) for item in result.scalars().all()]

        total_pages = max(1, ceil(total / page_size) if page_size > 0 else 1)
        return ProjectListPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    @staticmethod
    async def update_project(
        db: AsyncSession,
        project_id: UUID,
        tenant_id: UUID,
        request: ProjectUpdateRequest,
    ) -> ProjectORM:
        project = await get_project_by_id(db, project_id, tenant_id)
        if project is None:
            raise NotFoundError("Project")

        if request.code is not None and request.code != project.code:
            existing = await get_project_by_code(db, request.code, tenant_id)
            if existing is not None and existing.id != project.id:
                raise ConflictError("Project", "code", request.code)

        if request.name is not None:
            project.name = request.name
        if request.description is not None:
            project.description = request.description
        if request.code is not None:
            project.code = request.code
        if request.project_type is not None:
            project.project_type = request.project_type.value
        if request.status is not None:
            project.status = request.status.value
        if request.estimated_budget is not None:
            project.estimated_budget = request.estimated_budget
        if request.currency is not None:
            project.currency = request.currency
        if request.start_date is not None:
            project.start_date = request.start_date
        if request.end_date is not None:
            project.end_date = request.end_date
        if request.metadata is not None:
            project.metadata_json = request.metadata

        await db.commit()
        await db.refresh(project)
        return _attach_metadata_alias(project)

    @staticmethod
    async def delete_project(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> None:
        project = await get_project_by_id(db, project_id, tenant_id)
        if project is None:
            raise NotFoundError("Project")
        await db.delete(project)
        await db.commit()

    @staticmethod
    async def get_project_stats(db: AsyncSession, tenant_id: UUID) -> ProjectStats:
        projects_result = await db.execute(
            select(ProjectORM.status, ProjectORM.coherence_score).where(ProjectORM.tenant_id == tenant_id)
        )
        rows = projects_result.all()
        total = len(rows)
        draft = sum(1 for status, _ in rows if status == ProjectStatus.DRAFT.value)
        active = sum(1 for status, _ in rows if status == ProjectStatus.ACTIVE.value)
        completed = sum(1 for status, _ in rows if status == ProjectStatus.COMPLETED.value)
        archived = sum(1 for status, _ in rows if status == ProjectStatus.ARCHIVED.value)

        scored = [float(score) for _, score in rows if score is not None]
        avg_score = (sum(scored) / len(scored)) if scored else None

        return ProjectStats(
            total_projects=total,
            active_projects=active,
            draft_projects=draft,
            completed_projects=completed,
            archived_projects=archived,
            avg_coherence_score=avg_score,
        )
